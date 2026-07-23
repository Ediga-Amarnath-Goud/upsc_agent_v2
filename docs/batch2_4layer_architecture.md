# Batch 2 Blueprint — 4-Layer Architecture + Current Affairs

## Overview

This document defines the evolution of UPSC Agent V2 from a single-model (Batch 1)
system into a 4-layer multi-model architecture with an integrated Current Affairs
module. Each layer has a distinct responsibility, model, and execution model.

---

## System Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (React + Vite)                          │
│  Dashboard │ Upload │ Generate │ Session │ OMR │ Logs │ CA View │ Profile │
└────────────────────────────┬───────────────────────────────────────────────┘
                             │ HTTP (proxy /api → :8000)
┌────────────────────────────▼───────────────────────────────────────────────┐
│                           BACKEND (FastAPI)                                 │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │  Layer 1     │  │  Layer 2     │  │  Layer 3     │  │  Layer 4      │  │
│  │  OCR        │  │  Profile     │  │  Question    │  │  Critic       │  │
│  │  (Flash Lite)│  │  Analyst     │  │  Engine      │  │  (Sarvam AI)  │  │
│  │  Async       │  │  (Gemini 3.5)│  │  (DeepSeek   │  │  (Sarvam-105B)│  │
│  │             │  │  Async       │  │   V4 Pro)    │  │  Sync         │  │
│  │             │  │             │  │  Sync        │  │              │  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬────────┘  │
│         │                │                │                │            │
│  ┌──────▼────────────────▼────────────────▼────────────────▼──────────┐ │
│  │                    CURRENT AFFAIRS PARSER                            │ │
│  │              (Gemini 3.5 Flash — daily auto-fetch)                   │ │
│  └────────────────────────────┬─────────────────────────────────────────┘ │
│                               │                                           │
│  ┌────────────────────────────▼─────────────────────────────────────────┐ │
│  │                    DATABASE (SQLite)                                  │ │
│  │  upsc_agent.db  │  current_affairs.db  │  profile_analysis           │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## Layer 1 — OCR Module

**File**: `backend/ocr_layer.py`

**Model**: Gemini Flash Lite (`gemini-2.0-flash-lite`)

**Execution**: Asynchronous (background task)

**Purpose**: Text extraction from images — separate from existing PDF→Markdown pipeline.
Does NOT replace `pdf_to_md.py` (LlamaParse stays for PDF→Markdown).

### Functions

```python
def read_omr_sheet(image_bytes: bytes, total_questions: int) -> dict[int, str]
```

- Reads OMR sheet image, identifies filled bubbles (A/B/C/D per question)
- Returns mapping of question_index → response letter
- Replaces inline Gemini Vision logic in `main.py:submit-omr`

```python
def extract_mains_answer(image_bytes: bytes) -> str
```

- Extracts text from Mains answer sheet images (handwritten + typed)
- Returns raw extracted text for human or auto evaluation

### Integration Points

| Endpoint | Change |
|---|---|
| `POST /submit-omr` | Replace inline code with `ocr_layer.read_omr_sheet()` |
| `POST /ocr/mains-evaluate` | **New** — upload image, return extracted text |

---

## Layer 2 — Profile Analyst

**File**: `backend/profile_analyst.py`

**Model**: Gemini 3.5 Flash (`gemini-2.5-flash`)

**Execution**: Asynchronous — runs after test completion + on-demand via
`POST /analyze-profile`

**Purpose**: Deep analysis of ALL student data to identify topic-level strengths,
weaknesses, error patterns, and generate prescriptive improvement plans with
actionable study/practice/resource suggestions.

### Input Data

| Source | What it provides |
|---|---|
| `student_profile` | ELO, trap_stats, subject_trap_accuracy |
| `attempt_history` | ALL past attempts with correct/wrong, trap_type, time_taken |
| `question_analysis` | ALL analyzed questions (text, options, correct_key, trap_type, difficulty) |
| `trap_summary.json` | Aggregated trap patterns across all analyzed questions |

### Processing Pipeline

#### Step 1: Batch Topic Classification

Reads every `question_analysis` row and classifies it by topic + subtopic.
Only processes rows without an existing `question_topics` entry.

**Gemini prompt**: Classify each UPSC question into topic + subtopic.

```json
{"topic": "History", "subtopic": "Medieval India - Delhi Sultanate"}
```

Results stored in `question_topics` table.

#### Step 2: Per-Topic & Per-Subtopic Accuracy

Cross-references `attempt_history` with `question_topics` to compute accuracy
breakdown at topic and subtopic level.

```json
{
  "topic_accuracy": [
    {
      "topic": "History",
      "subtopic": "Ancient India - Mauryan Empire",
      "accuracy": 0.30,
      "attempted": 20,
      "correct": 6
    },
    {
      "topic": "Polity",
      "subtopic": "Fundamental Rights",
      "accuracy": 0.92,
      "attempted": 25,
      "correct": 23
    }
  ]
}
```

#### Step 3: Margin of Error Analysis

For each wrong answer, identifies the root cause category:

| Error Type | Description |
|---|---|
| **Trap susceptibility** | Fell for a known trap type (e.g., Misleading Chronology) |
| **Knowledge gap** | No understanding of the underlying concept |
| **Confusion pattern** | Consistently chooses a specific wrong option across related questions |

Detects cross-topic patterns: "You fall for 'Misleading Chronology' traps in
Modern History 70% of the time."

#### Step 4: Prescriptive Improvement Plans

For EACH identified weakness, generates a structured improvement plan:

```json
{
  "topic": "History",
  "subtopic": "Ancient India - Mauryan Empire",
  "accuracy": 0.30,
  "attempted": 20,
  "falling_trap": "Misleading Chronology",
  "improvement_plan": {
    "root_cause": "Confuses Mauryan and Gupta dynasty timelines",
    "study_suggestions": [
      "Create a timeline of Mauryan rulers from Chandragupta to Brihadratha",
      "Focus on Ashoka's edicts and their chronological order",
      "Compare Mauryan administration with Gupta administration"
    ],
    "practice_suggestions": [
      "Attempt 10 chronology-based questions on Mauryan period",
      "Focus on questions that mix Mauryan and post-Mauryan events"
    ],
    "resource_suggestions": [
      "RS Sharma Chapter 8-12 (Ancient India)",
      "NCERT Class XI - Ancient India: The Mauryan Empire"
    ]
  }
}
```

#### Step 5: Strengths Analysis

For each identified strength (accuracy >= 80%, >= 10 attempts):

```json
{
  "topic": "Polity",
  "subtopic": "Fundamental Rights",
  "accuracy": 0.92,
  "maintain_strategy": "Weekly revision through 5 questions to retain edge"
}
```

#### Step 6: Improvement Roadmap

Priority-ordered list of focus areas:

```json
{
  "improvement_roadmap": {
    "priority_1": "Ancient India - Mauryan Empire",
    "priority_2": "Modern India - National Movement (1920-1935)",
    "priority_3": "Numerical Illusion traps in Economy",
    "estimated_sessions_to_improve": 15
  }
}
```

#### Step 7: Narrative Coach Report

A human-readable report written in a tutor's voice:

> "You've attempted 200 questions. Your overall accuracy is 68%. Polity is your
> strongest area (92%) — maintain it with weekly revision. Your biggest gap is
> Ancient India, specifically the Mauryan period (30% accuracy). You consistently
> confuse Mauryan and Gupta timelines. Start with RS Sharma Chapters 8-12, then
> practice 10 chronology-based questions. I've prioritized this as your #1 focus.
> Expect improvement in about 15 practice sessions."

### Output Storage

All outputs stored in the `profile_analysis` table:

```sql
CREATE TABLE profile_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT REFERENCES student_profile(student_id),
    structured_data TEXT,       -- JSON: topic_accuracy, weaknesses, strengths,
                               -- improvement_plans, roadmap
    coach_report TEXT,          -- narrative report
    trigger_type TEXT,          -- post_test / manual
    question_count_at_analysis INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Question Topics Table (populated by Layer 2)

```sql
CREATE TABLE question_topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_analysis_id INTEGER REFERENCES question_analysis(id),
    topic TEXT,
    subtopic TEXT,
    confidence REAL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_qt_question ON question_topics(question_analysis_id);
CREATE INDEX idx_qt_topic ON question_topics(topic, subtopic);
```

### Triggers

| Trigger | When |
|---|---|
| **Auto** | After every test session completion (if >=10 new attempts since last analysis) |
| **Manual** | Via `POST /analyze-profile` endpoint |
| **Scheduled** | Weekly run via scheduler |

### API Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/analyze-profile` | Trigger async profile analysis |
| `GET` | `/profile/analysis` | Get latest coach report + structured data |

---

## Layer 3 — Question Engine

**Files**: `backend/generator.py`, `backend/analyze_traps.py`, `backend/pyq_analyzer.py`

**Model**: DeepSeek V4 Pro (via OpenRouter / `deepseek/deepseek-v4-pro`)

**Execution**: Synchronous (blocking API call during test generation)

**Purpose**: Question generation, trap analysis, and difficulty calibration.

### What Changes in `generator.py`

1. **Before generation**, fetch:
   - Latest `profile_analysis.structured_data` — inject recommended focus areas
     into the prompt
   - Relevant `current_affairs` entries matching the topic — inject for
     context-aware questions

2. **After DeepSeek returns**, pass through Layer 4 (Critic) before saving

### What Stays the Same

- `analyze_traps.py` — Keep using DeepSeek V4 Pro for trap analysis pipeline
- `pyq_analyzer.py` — Reference question sampling unchanged
- ELO math in `math_utils.py` — Unchanged (remains real-time Python, not LLM)

### Enhanced Prompt Structure

```
You are a UPSC Prelims paper setter. Generate {count} questions on "{topic}".

{RULES}

Student Profile Context:
- Weak areas to target: {profile_analysis.recommended_focus}
- Trap types to emphasize: {profile_analysis.trap_susceptibility}

Reference Current Affairs:
{relevant_ca_entries}

{REF_SECTION (PYQs)}

{PRIORITY_SECTION (ELO-based)}

Return JSON with questions and answer_key...
```

---

## Layer 4 — Critic Module

**File**: `backend/critic.py`

**Model**: Sarvam AI (`sarvam-105b`)

**API**: `https://api.sarvam.ai` (OpenAI-compatible, `/v1/chat/completions`)

**Auth**: `api-subscription-key` header

**Execution**: Synchronous — runs after DeepSeek generation, before response

**Cost**: ₹4/1M input, ₹2.5/1M cached, ₹16/1M output tokens (₹100 free credit)

### Flow

```
DeepSeek generates Q&A set → Critic reviews each question → quality verdict
  ├── pass → save and return
  ├── review → log warnings, save and return
  └── fail → regenerate flagged questions with critic feedback (max 2 retries)
```

### Critic Checks (per question)

| Check | What it evaluates |
|---|---|
| **Factual accuracy** | Is the question factually correct? Does the answer match established knowledge? |
| **Trap quality** | Is the trap type correctly identified? Is the mechanism explanation sound? |
| **Ambiguity** | Could a student interpret the question multiple ways? Are options distinct? |
| **Cultural/policy relevance** | Does it reflect Indian exam context correctly? (Sarvam's strength) |
| **Difficulty calibration** | Does the difficulty tier match actual complexity? |

### Output Format

```python
{
  "overall_verdict": "pass" | "review" | "fail",
  "per_question": [
    {
      "index": 0,
      "score": 0.85,
      "flags": [],
      "suggestion": ""
    },
    {
      "index": 1,
      "score": 0.45,
      "flags": ["factual_error", "ambiguous_wording"],
      "suggestion": "The Kalinga War was 261 BCE, not 265 BCE"
    }
  ]
}
```

### Integration

```python
# In generator.py — after DeepSeek response
if quality_check:
    from critic import review_question_set
    verdict = review_question_set(questions, answer_key)
    if verdict.overall_verdict == "fail":
        # regenerate flagged questions (max 2 retries)
        flagged_indices = [q.index for q in verdict.per_question if q.score < 0.6]
        questions, answer_key = regenerate_flagged(
            questions, answer_key, flagged_indices
        )
```

### API Endpoint Change

| Endpoint | Change |
|---|---|
| `POST /generate-test/prelims` | Add optional `quality_check=true/false` param (default: true) |

### Fallback

If Sarvam API is down or timeout:
- Log the failure
- Skip critic pass
- Return generated questions as-is (current Batch 1 behavior)

---

## Current Affairs Module

**Files**: `backend/current_affairs.py`

**Model**: Gemini 3.5 Flash (for parsing/structuring content)

**Database**: `data/current_affairs.db` (separate SQLite file)

**Execution**: Scheduled daily auto-fetch + manual ingestion endpoints

### Data Sources

Configured via `NEWS_SOURCES` env var (comma-separated):

| Source | RSS Feed(s) | Type |
|---|---|---|
| The Hindu | National, Opinion/Editorials, International, Sci-Tech | Newspaper |
| Indian Express | Editorials, Explained, UPSC CA, Political Pulse | Newspaper |
| PIB | English Releases, Features | Government |
| Economic Times | India, Politics | Newspaper |
| Business Standard | Economy, Politics, Current Affairs | Newspaper |

### Daily Fetch Pipeline

```python
# 1. Fetch RSS feeds
import feedparser
feed = feedparser.parse(url)
for entry in feed.entries:
    if exists_in_db(entry.link):
        continue  # dedup by source_url UNIQUE constraint

# 2. Extract full article text
from newspaper import Article
article = Article(entry.link)
article.download()
article.parse()
full_text = article.text

# 3. Structure with Gemini 3.5 Flash
result = gemini_client.generate_content(
    f"Analyze this news article for UPSC relevance:\n\n{full_text}\n\n"
    "Return JSON with: title, summary (100-150 words), category "
    "(Polity/Economy/Geography/Environment/Science/International/"
    "Social/Culture/Security), "
    "tags (5-10 keywords), key_facts (array of important facts, data points, "
    "committee names), upsc_relevance (high/medium/low), date_of_event"
)

# 4. Store in DB
INSERT INTO current_affairs (...)
```

### Database Schema (`current_affairs.db`)

```sql
CREATE TABLE current_affairs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    source TEXT,
    source_url TEXT UNIQUE,
    full_text TEXT,
    summary TEXT,
    category TEXT,
    tags TEXT,              -- JSON array
    key_facts TEXT,         -- JSON array
    upsc_relevance TEXT,    -- high / medium / low
    date_of_event DATE,
    is_editorial BOOLEAN DEFAULT 0,
    newspaper_name TEXT,
    date_fetched DATE DEFAULT CURRENT_DATE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ca_category ON current_affairs(category);
CREATE INDEX idx_ca_date ON current_affairs(date_of_event);
CREATE INDEX idx_ca_relevance ON current_affairs(upsc_relevance);
```

### Scheduler

```python
# Using schedule library (or background thread)
import schedule

def daily_fetch():
    sources = os.environ.get("NEWS_SOURCES", "").split(",")
    for source in sources:
        fetch_and_parse_source(source.strip())

schedule.every().day.at("06:00").do(daily_fetch)
```

Triggered at startup if >24 hours since last fetch.

### API Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/current-affairs` | List with filters: `?category=&search=&date_from=&date_to=&relevance=&page=&per_page=` |
| `GET` | `/current-affairs/:id` | Single entry detail |
| `GET` | `/current-affairs/:id/pdf` | Download as PDF (fpdf2) |
| `POST` | `/current-affairs/ingest` | Manually add text/URL → parse with Gemini |
| `POST` | `/current-affairs/fetch` | Trigger immediate fetch from all sources |
| `GET` | `/current-affairs/stats` | Count by category, recent activity |

### Frontend View

**File**: `frontend/src/pages/CurrentAffairs.jsx`

| Feature | Description |
|---|---|
| **List view** | Cards with title, summary preview, category badge, date, relevance badge |
| **Search bar** | Full-text search across title, summary, tags |
| **Category filter** | Dropdown with all categories |
| **Date range picker** | Filter by date_of_event range |
| **Relevance filter** | high / medium / low |
| **Detail modal** | Full summary, key facts list, source link, tags |
| **PDF download** | Per-entry button + bulk download for date range |
| **Manual ingestion** | Form with textarea + parse button |

### PDF Generation

```python
# In current_affairs.py or reuse pdf_generator.py
def generate_ca_pdf(entries: list[dict], output_path: str):
    """Generate a formatted PDF with title, date, summary, key facts per entry"""
```

### Question Generation Integration

In `generator.py`, before building the prompt:

```python
from current_affairs import get_relevant_entries

ca_entries = get_relevant_entries(topic, limit=5)
if ca_entries:
    prompt_context = "\n\nReference Current Affairs:\n"
    for ca in ca_entries:
        prompt_context += (
            f"- [{ca['category']}] {ca['title']}\n"
            f"  Summary: {ca['summary']}\n"
            f"  Key facts: {ca['key_facts']}\n"
        )
```

---

## New & Modified Database Tables

### New Tables

```sql
-- Profile Analysis (in upsc_agent.db)
CREATE TABLE profile_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT REFERENCES student_profile(student_id),
    structured_data TEXT,
    coach_report TEXT,
    trigger_type TEXT,
    question_count_at_analysis INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Question Topics (in upsc_agent.db)
CREATE TABLE question_topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_analysis_id INTEGER REFERENCES question_analysis(id),
    topic TEXT,
    subtopic TEXT,
    confidence REAL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_qt_question ON question_topics(question_analysis_id);
CREATE INDEX idx_qt_topic ON question_topics(topic, subtopic);
```

```sql
-- Current Affairs (in current_affairs.db — separate file)
CREATE TABLE current_affairs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    source TEXT,
    source_url TEXT UNIQUE,
    full_text TEXT,
    summary TEXT,
    category TEXT,
    tags TEXT,
    key_facts TEXT,
    upsc_relevance TEXT,
    date_of_event DATE,
    is_editorial BOOLEAN DEFAULT 0,
    newspaper_name TEXT,
    date_fetched DATE DEFAULT CURRENT_DATE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ca_category ON current_affairs(category);
CREATE INDEX idx_ca_date ON current_affairs(date_of_event);
CREATE INDEX idx_ca_relevance ON current_affairs(upsc_relevance);
```

---

## New & Modified Files

### New Backend Files

| File | Purpose |
|---|---|
| `backend/ocr_layer.py` | Layer 1 — OMR reading + Mains answer extraction |
| `backend/profile_analyst.py` | Layer 2 — Deep student profile analysis |
| `backend/critic.py` | Layer 4 — Sarvam AI quality review |
| `backend/current_affairs.py` | CA fetcher, parser, CRUD, PDF generation |

### Modified Backend Files

| File | Change |
|---|---|
| `backend/main.py` | New endpoints + modified submit-omr + modified generate-test |
| `backend/generator.py` | Inject profile analysis + current affairs; add critic pass |
| `backend/models.py` | Add profile_analysis + question_topics tables |
| `backend/database.py` | Add current_affairs.db connection |
| `backend/requirements.txt` | Add feedparser, newspaper3k, schedule |

### New Frontend Files

| File | Purpose |
|---|---|
| `frontend/src/pages/CurrentAffairs.jsx` | Current affairs list + detail + filters |
| `frontend/src/pages/ProfileAnalysis.jsx` | Coach report view + recommendations |

### Modified Frontend Files

| File | Change |
|---|---|
| `frontend/src/App.jsx` | Add CA route + Profile Analysis route |
| `frontend/src/hooks/useQueries.js` | Add current-affairs + profile-analysis queries |
| `frontend/src/hooks/useMutations.js` | Add ingest/fetch mutations |

---

## New & Modified API Endpoints

| Method | Path | Layer | Status |
|---|---|---|---|
| `POST` | `/ocr/mains-evaluate` | L1 | **New** |
| `POST` | `/submit-omr` | L1 | Modified (use ocr_layer) |
| `POST` | `/analyze-profile` | L2 | **New** |
| `GET` | `/profile/analysis` | L2 | **New** |
| `POST` | `/generate-test/prelims` | L3+L4 | Modified (add critic + CA) |
| `GET` | `/current-affairs` | CA | **New** |
| `GET` | `/current-affairs/:id` | CA | **New** |
| `GET` | `/current-affairs/:id/pdf` | CA | **New** |
| `POST` | `/current-affairs/ingest` | CA | **New** |
| `POST` | `/current-affairs/fetch` | CA | **New** |
| `GET` | `/current-affairs/stats` | CA | **New** |

---

## Environment Variables

Add to `backend/.env`:

```env
# Layer 1 — OCR
OCR_MODEL=gemini-2.0-flash-lite

# Layer 2 — Profile Analyst
PROFILE_MODEL=gemini-2.5-flash

# Layer 4 — Critic (Sarvam AI)
SARVAM_API_KEY=sarv_...
SARVAM_MODEL=sarvam-105b
SARVAM_BASE_URL=https://api.sarvam.ai

# Current Affairs
NEWS_SOURCES=hindu_editorials,hindu_national,indianexpress_editorials,indianexpress_explained,pib,et_india
CA_FETCH_INTERVAL_HOURS=24
CA_MAX_PER_FETCH=50
```

---

## Dependencies

Add to `backend/requirements.txt`:

```
feedparser>=6.0.0
newspaper3k>=0.2.8
schedule>=1.2.0
```

Sarvam AI is called via direct HTTP requests (OpenAI-compatible), no SDK needed.

---

## Implementation Order

| Phase | Module | Duration | Depends On |
|---|---|---|---|
| 1 | `current_affairs.py` + DB + endpoints | 4-5 days | None |
| 2 | `current_affairs.py` — PDF gen + scheduler | 1-2 days | Phase 1 |
| 3 | Frontend: `CurrentAffairs.jsx` | 2-3 days | Phase 1-2 |
| 4 | `ocr_layer.py` — OMR + Mains OCR | 2 days | None |
| 5 | Update `submit-omr` to use ocr_layer | 0.5 day | Phase 4 |
| 6 | `profile_analyst.py` + question_topics table | 3-4 days | None |
| 7 | Profile analysis endpoints + triggers | 1 day | Phase 6 |
| 8 | Frontend: `ProfileAnalysis.jsx` | 1-2 days | Phase 7 |
| 9 | `critic.py` — Sarvam AI integration | 2 days | None |
| 10 | Wire critic into `generator.py` | 1 day | Phase 9 |
| 11 | Wire CA into `generator.py` | 0.5 day | Phase 1-2 |
| 12 | Wire profile analysis into `generator.py` | 0.5 day | Phase 6-7 |
| 13 | Integration testing + bug fixes | 2-3 days | All phases |

**Total estimated time**: ~21-26 days

---

## Fallback & Error Handling

| Scenario | Fallback |
|---|---|
| Sarvam API down/timeout | Skip critic, proceed with generated questions, log failure |
| Current Affairs fetch fails for one source | Log error, continue with other sources |
| Profile analysis Gemini call fails | Retry once, log failure, skip analysis for this cycle |
| OCR quality low (handwriting confidence < threshold) | Return text with confidence score, flag for human review |
| Duplicate CA entry (same URL) | `source_url UNIQUE` constraint handles it silently |

---

## Edge Cases

| Scenario | Handling |
|---|---|
| Empty current affairs DB at startup | Generator runs without CA context — graceful degradation |
| First-time student (no attempts) | Profile analyst returns "insufficient data" message; generator uses default ELO priority matrix |
| No RSS feed content on a given day | Scheduler logs "no new entries", skips Gemini call |
| Very long articles (>LLM context) | Truncate to first 8000 chars before sending to Gemini |
| OMR with unclear/multiple bubbles | Mark as null; skip in scoring; log warning |
| Critic and generator disagree persistently | After 2 retries, accept current version and log disagreement |
