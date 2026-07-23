# UPSC Agent v2 — System Architecture

## Overview

A full-stack UPSC Prelims preparation platform built around PYQ (Previous Year Question) analysis, AI-powered test generation, diagnostic testing, adaptive learning via ELO ratings, trap-based pedagogy, and automated current affairs ingestion. Uses a React frontend with a FastAPI backend and SQLite databases.

---

## Tech Stack

| Layer         | Technology                            |
|---------------|---------------------------------------|
| **Frontend**  | React 19, Tailwind CSS, Vite, React Router, Axios |
| **Backend**   | FastAPI (Python 3.12+), SQLAlchemy, SQLite |
| **AI**        | Google Gemini API (`gemini-2.5-flash`, `gemini-3-flash-preview`, `gemini-3.1-flash-lite`), Sarvam AI, Deepseek API (via OpenRouter), LlamaParse |
| **PDF**       | `fpdf` (question papers, answer keys, CA digests) |
| **OCR**       | Gemini vision (OMR sheet reading, Mains answer extraction) |
| **RSS**       | `feedparser` for news aggregation |
| **Articles**  | `newspaper3k` for article scraping |
| **PDF->MD**   | LlamaParse (for CA PDF/materials processing) |
| **Scheduling**| `threading.Timer` for recurring CA fetch (every 6h) |

---

## Directory Layout

```
upsc_agent_v2/
├── backend/
│   ├── main.py                   # FastAPI app, 30+ routes, middleware, startup scheduler
│   ├── models.py                 # 9 SQLAlchemy ORM models (main DB + CA DB)
│   ├── database.py               # Two SQLite DBs (main + current_affairs), migration, WAL mode
│   ├── schemas.py                # Pydantic models for request/response validation
│   ├── model_config.py           # Per-layer model selection + tier mapping
│   ├── api_guardrail.py          # Two-tier rate limiter + Gemini client factory
│   ├── math_utils.py             # Dynamic ELO (K=40/25/15/10), trap stats, priority matrix
│   ├── diagnostic.py             # 60-question diagnostic (25 PYQs + 35 AI-generated), grading
│   ├── generator.py              # Adaptive test generation with PYQ references + CA context
│   ├── critic.py                 # Quality review via Sarvam AI (primary) + Gemini (fallback)
│   ├── pdf_generator.py          # `fpdf` question paper & answer key PDFs
│   ├── profile_analyst.py        # Keyword classification + Gemini coach reports
│   ├── ocr_layer.py              # Gemini vision for OMR sheets + Mains answer sheets
│   ├── current_affairs.py        # 703-line CA pipeline: RSS→Sarvam filter→Gemini parse→store→PDF digest
│   ├── analyze_traps.py          # Batch PYQ trap analysis (Gemini/Deepseek), chunked processing
│   ├── pyq_analyzer.py           # Reference question retrieval for generator
│   ├── build_trap_summary.py     # Aggregates trap_type statistics across all analyzed questions
│   ├── extract_questions.py      # Parses markdown into structured question dicts
│   ├── pdf_to_md.py              # PDF→markdown conversion (Gemini vision or pypdf fallback)
│   ├── deepseek_api.py           # Deepseek batch API client (for trap analysis)
│   ├── fetch_answer_keys.py     # Downloads official UPSC answer keys from prepp.in PDFs
├── verify_answers.py         # Cross-checks Gemini answers against official UPSC keys
│   ├── verify_answers.py         # Cross-checks Gemini answers against official keys
│   ├── test_*.py / reanalyze_*.py / run_*.py  # Standalone scripts for pipeline testing
│   ├── logger.py                 # Logging config — per-module file + stdout loggers
│   └── data/                     # Local storage: DB, PDFs, uploads, images, markdown
├── frontend/
│   ├── src/
│   │   ├── main.jsx              # Entry point
│   │   ├── App.jsx               # Router with onboarding gate (splash→welcome→profile→consent→diagnostic→dashboard)
│   │   ├── index.css             # Tailwind with custom glassmorphism theme
│   │   ├── api/client.js         # Axios instance with /api prefix
│   │   ├── hooks/
│   │   │   ├── useQueries.js     # React Query wrappers for GET endpoints
│   │   │   └── useMutations.js   # React Query wrappers for POST endpoints
│   │   ├── utils/format.js       # Formatting helpers (dates, scores, etc.)
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── Layout.jsx    # Full app shell with sidebar + topbar
│   │   │   │   ├── Sidebar.jsx   # Navigation sidebar
│   │   │   │   └── TopBar.jsx    # Top bar with user info
│   │   │   ├── cards/            # Dashboard card components (13 cards)
│   │   │   │   ├── ActiveSession.jsx
│   │   │   │   ├── TodaysMission.jsx
│   │   │   │   ├── PendingPYQs.jsx
│   │   │   │   ├── BacklogsDue.jsx
│   │   │   │   ├── SessionStatus.jsx
│   │   │   │   ├── SubjectProgress.jsx
│   │   │   │   ├── PerformanceSnapshot.jsx
│   │   │   │   ├── WeeklyHeatmap.jsx
│   │   │   │   ├── StudyHours.jsx
│   │   │   │   ├── QuickActions.jsx
│   │   │   │   ├── SystemOperations.jsx
│   │   │   │   ├── RecentActivity.jsx
│   │   │   │   └── ... (5 more)
│   │   │   └── ui/               # Reusable UI primitives
│   │   │       ├── GlassCard.jsx
│   │   │       ├── CircularProgress.jsx
│   │   │       ├── ProgressBar.jsx
│   │   │       ├── StatusBadge.jsx
│   │   │       ├── KPINumber.jsx
│   │   │       └── LoadingSpinner.jsx
│   │   └── pages/
│   │       ├── SplashScreen.jsx       # Landing page with "Get Started"
│   │       ├── WelcomeScreen.jsx      # Brief intro carousel
│   │       ├── CreateProfile.jsx      # Name, age, gender form
│   │       ├── ConsentScreen.jsx      # Diagnostic consent
│   │       ├── Diagnostic.jsx         # 60-question CBT with 60-min timer, voice input
│   │       ├── Dashboard.jsx          # 4-column grid of 13 cards
│   │       ├── GenerateTest.jsx       # Topic-based test generation
│   │       ├── SessionView.jsx        # Live test-taking or review mode
│   │       ├── UploadPDF.jsx          # PYQ PDF upload
│   │       ├── MyTests.jsx            # History of all tests + diagnostic
│   │       ├── OMRUpload.jsx          # OMR sheet scanning
│   │       ├── Logs.jsx               # Activity logs
│   │       ├── CurrentAffairs.jsx     # CA listing with filters
│   │       ├── CADetail.jsx           # Single CA article + PDF download
│   │       ├── ProfileAnalysis.jsx    # Coach report + analysis display
│   │       └── MainsOcr.jsx           # Mains answer evaluation
│   └── ...config files
```

---

## Database: Two separate SQLite databases

### Main DB (`data/upsc_agent.db`)

#### `ActivityLog`
Tracks PYQ PDF upload processing pipeline stages (uploaded → llamaparse → extracting → analyzing → complete/failed).

#### `QuestionAnalysis`
Core PYQ storage. One row per analyzed question with: full text, 4 options, correct_key, verified_answer (from official key), trap_type, trap_mechanism, distraction_analysis (which wrong option is most tempting and why), related_concepts, difficulty_tier (1-10). Populated by `analyze_traps.py`.

#### `QuestionTopics`
Keyword-classified subject assignments for each `QuestionAnalysis`. Populated by `profile_analyst.py._classify_unclassified()`.

#### `StudentProfile`
Single-row student state (student_id = "default"). Fields: current_elo (1200 base), subject_elos (per-subject ELO), total_attempted/correct, trap_stats (trap_type → {encountered, correct, wrong}), subject_trap_accuracy (subject → trap_type → stats with trajectory), per_subject_accuracy, diagnostic_completed flag.

#### `TestSession`
One row per generated practice test. Stores questions (JSON), answer_key (JSON), responses (JSON), score, status, pdf_path, answer_key_path.

#### `AttemptHistory`
Individual answer attempts with session_id, question_index, response, correct boolean, time_taken, trap_type.

#### `DiagnosticQuestions`
60-question pool (25 PYQs + 35 generated) used for diagnostic tests. Fields: question_text, options, correct_key, subject, difficulty_tier, trap_type, source ("pyq"|"generated"), ca_reference.

#### `DiagnosticResults`
One per diagnostic session. Stores question_ids (ordered list), responses dict, score, total, per_subject breakdown, pdf_path, answer_key_path, started_at, time_taken.

#### `ProfileAnalysis`
Snapshot of structured analysis + AI coach report. Triggered manually. Fields: structured_data (JSON text), coach_report (plain text), trigger_type, question_count_at_analysis.

### Current Affairs DB (`data/current_affairs.db`)

#### `CurrentAffairs`
Stores fetched news articles. Fields: title, source, source_url (unique), full_text, summary, category, subject, tags (JSON), key_facts (JSON), historical_context, upsc_relevance (high/medium/low), image_url, image_path, date_of_event, is_editorial, newspaper_name, date_fetched.

---

## Key Flows

### 1. Onboarding Pipeline (Frontend gateway)
1. `/` → `SplashScreen` → "Get Started"
2. `/welcome` → `WelcomeScreen` → brief intro
3. `/create-profile` → POST `/api/profile/create` (name, age, gender)
4. `/consent` → `ConsentScreen` → agree to diagnostic
5. `/diagnostic` → 60-question CBT (standalone, no sidebar)
6. After submit → redirects to `/` → full `Layout` (sidebar + topbar) with `Dashboard`

The onboarding is enforced by an ASGI middleware in `main.py` that checks `student_profile.diagnostic_completed`. Unauthenticated requests to non-onboarding paths return 403 with redirect hints.

### 2. PYQ Ingestion Pipeline
1. User uploads PDF via `POST /upload-pdf` (max 50MB)
2. Background `process_pdf_pipeline()` runs:
   - `pdf_to_md.py` → converts PDF to markdown (Gemini vision, fallback pypdf)
   - `extract_questions.py` → parses markdown into structured question dicts
   - Loads official answer key from `data/answer_keys/{year}.json` if year detected
   - `analyze_traps.py` → batch Gemini/Deepseek analysis (20 questions/batch) with retry + fallback
   - `build_trap_summary.py` → aggregates trap type statistics
3. Each question stored in `QuestionAnalysis` with trap metadata

### 3. Diagnostic Test
**Build (`build_diagnostic_bank` in `diagnostic.py`)**
- Selects up to 25 PYQs from `QuestionAnalysis` where trap_type is non-null
- Distributes across 7 subjects via `SUBJECT_KEYWORDS` keyword matching
- Target: Polity=5, History=5, Economy=3, Geography=3, Environment=3, Science=3, Culture=3
- Idempotent — skips if bank exists

**Generation (`generate_diagnostic_set`)**
- Gemini generates 35 fresh questions via `GENERATION_PROMPT` (ThinkingConfig, 65536 max tokens)
- Covers 7 subjects at varying difficulty (tier 1-10), at least 8 current affairs (2025-2026)
- Validates: 4 unique non-empty options, deduplicates by >85% text similarity
- Shuffles all 60 questions, persists session→question mapping
- Generates PDFs (question paper + answer key) via `fpdf` (best-effort, fails gracefully)

**Grading (`grade_diagnostic`)**
- Validates session exists, not already submitted, within 1-hour limit
- Updates StudentProfile: ELO (overall + per-subject), trap stats, per-subject accuracy
- **Score is NOT returned to frontend** — hidden; used only for AI coach

### 4. Adaptive Test Generation (`generator.py`)
- `POST /generate-test/prelims` with `{topic_studied, question_count, quality_check}`
- `_build_reference_section()`: fetches up to 5 related PYQs from DB for difficulty calibration
- `_build_priority_section()`: uses `math_utils.get_priority_matrix()` to generate slot-based trap targeting (60% weakest traps, 30% maintenance, 10% confidence)
- Injects current affairs context via `get_relevant_entries()`
- Gemini generates questions + answer key in one call
- Optional quality check via `critic.py` (Sarvam AI primary, Gemini fallback) — flags low-quality questions but accepts anyway
- Generates PDFs; stores in `TestSession`

### 5. Practice / CBT Interface
- `GET /session/{id}/data` → loads questions for test-taking
- `POST /submit-answer` → submits one answer at a time:
  - Validates no duplicates, builds response map
  - Updates ELO via `math_utils.compute_elo_update()` (dynamic K-factor)
  - Updates trap_stats + subject_trap_accuracy via `update_subject_trap_accuracy()`
  - Tracks trajectory (last 5 answers) per subject-trap combo
  - Stores in `AttemptHistory`
  - Auto-completes session when all questions answered
- `POST /submit-omr` → OMR sheet image → Gemini vision → batch answer submission

### 6. Profile Analysis (`profile_analyst.py`)
- Triggered via `POST /analyze-profile`
- Requires minimum 50 attempted questions
- Classifies unclassified questions via keyword matching (zero API cost)
- Computes: weaknesses (accuracy < 50% AND ELO < 1200), strengths (accuracy >= 80%)
- Identifies top 5 trap types by weakness score
- Gemini 2.5 Flash generates 300-500 word coach report with:
  - Overall assessment, subject breakdown, trap pattern analysis
  - Actionable study plan with specific topics and resources
- Results stored in `ProfileAnalysis`, viewable at ProfileAnalysis page

### 7. Current Affairs Pipeline (`current_affairs.py`)
- Startup scheduler fetches every 6 hours (daemon thread with `threading.Timer`)
- **Pipeline**: RSS feeds (6 sources) → dedup (title similarity >0.6) → Sarvam AI relevance filter → Gemini batch ranking (top 25) → article download (newspaper3k) → Gemini parse (category, subject, tags, key_facts, historical_context, upsc_relevance) → image selection → store
- Sarvam AI pre-filter: classifies articles as RELEVANT/NOT for UPSC to reduce API costs
- CA filter prompt evolves via LlamaParse + Gemini analysis of academy PDF materials
- End-of-day digest PDF auto-generated with subject sections, images, relevance badges
- REST endpoints: list with filters (category, relevance, search, date range), detail view, PDF download, manual ingest (URL or text), PDF upload for academy materials

### 8. OMR/Mains OCR (`ocr_layer.py`)
- `read_omr_sheet()`: Gemini vision identifies filled bubbles (A/B/C/D/null) from OMR image
- `extract_mains_answer()`: Gemini vision extracts handwritten/typed text from Mains answer sheet
- Both use `response_mime_type="application/json"` for structured output

### 9. API Guardrail (`api_guardrail.py`)
Two-tier rate limiter with JSON-persisted daily counters:

| Tier | RPM | Daily Max | Used By |
|------|-----|-----------|---------|
| **tier1_scarce** | 5 | 20 | coach, engine, critic |
| **tier2_abundant** | 15 | 500 | diagnostic, ocr, ca_parser, ca_analysis |

DeepSeek has its own independent guardrail (`deepseek_api.py`): 50 calls/day, 20 RPM — used only for PYQ trap analysis.

Per-layer model selection via `model_config.py`:

| Layer | Model | Tier |
|-------|-------|------|
| diagnostic | `gemini-3-flash-preview` | abundant |
| ocr | `gemini-3.1-flash-lite` | abundant |
| coach | `gemini-2.5-flash` | scarce |
| engine | `gemini-3-flash-preview` | scarce |
| critic | `gemini-3.1-flash-lite` | scarce |
| ca_parser | `gemini-3.1-flash-lite` | abundant |
| ca_analysis | `gemini-3-flash-preview` | abundant |

### 10. ELO Rating System (`math_utils.py`)

**Dynamic K-factor** (not static):
| Attempts | K |
|----------|---|
| < 30     | 40 |
| < 100    | 25 |
| < 300    | 15 |
| 300+     | 10 |

- Question rating: `800 + (difficulty_tier × 100)` (range 900–1800)
- Expected score: standard logistic function with scale factor 400
- ELO bounds: [400, 2000]
- `update_trap_stats(trap_stats, trap_type, correct)`: maintains `{encountered, correct, wrong}`
- `update_subject_trap_accuracy()`: per-subject trap tracking with last-5 trajectory (up/flat/down)
- `get_weakest_traps()`: weakness = `(1 - accuracy) × ln(encountered + 1)` with trajectory penalties (+30% for down, -20% for up)
- `get_priority_matrix()`: generates ordered practice slots (60% weak traps, 30% maintenance, 10% confidence)

---

## API Endpoints

### Onboarding & Profile
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check with model name |
| `/profile/create` | POST | Create student profile (name, age, gender) |
| `/profile/status` | GET | Check registration + diagnostic status |
| `/profile` | GET | Full profile with ELO, accuracy, attempts |
| `/analyze-profile` | POST | Trigger profile analysis |
| `/profile/analysis` | GET | Get latest coach report + structured data |

### Diagnostic
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/diagnostic` | GET | Generate or retrieve diagnostic set (60 questions) |
| `/diagnostic/submit` | POST | Submit diagnostic responses + optionally create profile |
| `/diagnostic/answer-key` | GET | Download answer key PDF |
| `/diagnostic/question-paper` | GET | Download question paper PDF |

### Practice Tests
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/generate-test/prelims` | POST | Generate adaptive test on a topic |
| `/session/{id}/data` | GET | Get session questions + responses |
| `/session/{id}/question-paper` | GET | Download question paper PDF |
| `/session/{id}/answer-key` | GET | Download answer key PDF |
| `/submit-answer` | POST | Submit single answer with ELO update |
| `/submit-omr` | POST | Submit OMR sheet image for batch grading |
| `/tests` | GET | List all tests (practice + diagnostic) + CA digests |

### OCR
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/ocr/mains-evaluate` | POST | Evaluate Mains answer sheet image |

### PDF Upload
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/upload-pdf` | POST | Upload PYQ PDF for analysis |
| `/activity-log` | GET | List all upload processing logs |
| `/activity-log/{id}` | GET | Single log detail |
| `/trap-summary` | GET | Aggregated trap type summary |

### Current Affairs
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/current-affairs` | GET | List with filters (category, relevance, search, date, page) |
| `/current-affairs/{id}` | GET | Single entry detail |
| `/current-affairs/{id}/pdf` | GET | Download single article PDF |
| `/current-affairs/fetch` | POST | Trigger manual CA fetch |
| `/current-affairs/ingest` | POST | Manual article ingest (URL or text) |
| `/current-affairs/upload-pdf` | POST | Upload academy PDF for analysis |
| `/current-affairs/stats` | GET | CA stats (total, today, by_category, by_relevance) |
| `/current-affairs/digest/pdf` | GET | Download today's digest PDF |

---

## Frontend Routing

| Route | Component | Auth | Notes |
|-------|-----------|:----:|-------|
| `/` | `SplashScreen` | No | If not registered |
| `/` | `Dashboard` | Yes | After onboarding complete |
| `/welcome` | `WelcomeScreen` | No | Onboarding step 1 |
| `/create-profile` | `CreateProfile` | No | Onboarding step 2 |
| `/consent` | `ConsentScreen` | No | Onboarding step 3 |
| `/diagnostic` | `Diagnostic` | No | Standalone mode (no sidebar) |
| `/upload` | `UploadPDF` | Yes | PYQ upload |
| `/generate-test` | `GenerateTest` | Yes | Topic input form |
| `/session` / `/session/:id` | `SessionView` | Yes | Test-taking & review |
| `/submit-omr` | `OMRUpload` | Yes | OMR sheet scanning |
| `/my-tests` | `MyTests` | Yes | Test history |
| `/logs` | `Logs` | Yes | Upload pipeline logs |
| `/current-affairs` | `CurrentAffairs` | Yes | CA listing |
| `/current-affairs/:id` | `CADetail` | Yes | Article detail |
| `/profile-analysis` | `ProfileAnalysis` | Yes | Coach report |
| `/mains-ocr` | `MainsOcr` | Yes | Mains answer eval |

---

## Frontend Architecture

- **State management**: React Query (`@tanstack/react-query`) via `useQueries.js` / `useMutations.js`
- **API client**: Axios instance with base URL `/api` and JSON defaults (`api/client.js`)
- **Styling**: Tailwind CSS with custom dark theme using CSS custom properties:
  - `--color-bg-primary: #0A0A0A`
  - `--color-bg-secondary: #141414`
  - `--color-bg-tertiary: #1E1E1E`
  - Accent colors: blue (`#4A90FF`), green (`#00C853`), amber, red
  - Glassmorphism effects: `backdrop-filter: blur(20px)` with semi-transparent backgrounds
- **Theming**: Multiple glass card variants (solid, glass, bordered) via `GlassCard.jsx`
- **Dashboard**: 4-column auto-rows grid layout with 13 card components, each independently fetching data

---

## Subject Classification

Three separate keyword maps across the codebase:

1. `diagnostic.py:SUBJECT_KEYWORDS` — 7 subjects with ~20 keywords each, used for PYQ classification in diagnostic bank building
2. `profile_analyst.py:SUBJECT_KEYWORDS` — 7 subjects, used for question topic classification
3. `main.py:SUBJECT_MAP` — Simple topic→subject mapping for test generation routing

Subjects: Polity, History, Economy, Geography, Environment, Science, Culture

---

## Key Design Decisions

1. **Dual database design**: Main DB and Current Affairs DB are separate SQLite files — CA has different update frequency and doesn't need to join with student data

2. **Score hidden from students**: Diagnostic results stored but never displayed — prevents discouragement and gaming. Only the AI coach uses the data.

3. **Dynamic ELO K-factor**: Higher K for new students (faster adaptation), lower for experienced (stable ratings)

4. **Trap-focused pedagogy with trajectory tracking**: System tracks which traps each student falls for, per subject, with last-5 trajectory to detect trends (improving/worsening)

5. **Priority matrix for adaptive tests**: 60% of practice questions target known weaknesses, 30% maintain existing skills, 10% build confidence

6. **Multi-model AI architecture**: Different Gemini models for different tasks — expensive reasoning (2.5 Flash) only for coaching, cheap models (3.1 Flash Lite) for OCR and CA parsing

7. **Sarvam AI as primary critic**: Quality checks use Sarvam AI first (cheaper/faster for structured eval), Gemini as fallback

8. **CA pipeline with evolving filter**: Sarvam pre-filter learns from academy PDFs — filter prompt evolves via LlamaParse → Gemini analysis cycle

9. **PDF generation as best-effort**: If PDF generation fails, the web experience still works

10. **Onboarding gateway middleware**: Blocks access to main app until diagnostic is completed, ensuring every student has baseline data

11. **Chunked batch processing**: PYQ analysis processes 20 questions per API call with retries + exponential backoff — avoids token limits

12. **Dual AI backend for PYQ analysis**: `analyze_traps.py` supports both Gemini and Deepseek (via OpenRouter) — configurable per run

13. **DeepSeek independent guardrail**: Separate rate limiter (`deepseek_api.py`: 50 calls/day, 20 RPM) with JSON-persisted daily counter

14. **No authentication**: The system uses a single "default" student_id with no user accounts — Supabase was not implemented
