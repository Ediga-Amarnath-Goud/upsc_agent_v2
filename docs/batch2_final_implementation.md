# Batch 2 Final — Implementation Plan

## Architecture

```
                    ┌──────────────────────────────────────┐
                    │            FRONTEND                   │
                    └──────────────────┬───────────────────┘
                                       │ HTTP
                    ┌──────────────────▼───────────────────┐
                    │          GATE (main.py)               │
                    │  Checks diagnostic_completed flag     │
                    │  Blocks if False (except /diagnostic) │
                    └──────────────────┬───────────────────┘
                                       │
  ┌──────────┬──────────────┬──────────────┬──────────────┬──────────────┐
  │ L0: Dx   │ L1: OCR      │ L2: Coach    │ L3: Q.Engine │ L4: Critic   │
  │ 3 Flash  │ 3.1 FL       │ 2.5 Flash    │ 3 Flash      │ Sarvam 105B  │
  │          │              │ (async,      │ (sync,       │ (sync,       │
  │          │              │  scheduled)  │  thinking)   │  fb:3 Flash) │
  └──────────┴──────┬───────┴──────┬───────┴──────┬───────┴──────┬───────┘
                     │              │              │              │
                     └──────┬───────┴──────┬───────┴──────┬───────┘
                     ┌──────▼──────────────▼──────────────▼──────────┐
                     │         CA PARSER (3.1 Flash Lite)             │
                     └──────────────────────┬─────────────────────────┘
                     ┌──────────────────────▼─────────────────────────┐
                     │              DATABASE (SQLite)                  │
                     │  upsc_agent.db  │  current_affairs.db          │
                     └────────────────────────────────────────────────┘
```

## Layer Assignments

| Layer | Module | Model | Tier | RPM/RPD | Execution |
|---|---|---|---|---|---|
| **L0** | `diagnostic.py` | `gemini-3-flash-preview` | Scarce | 5/20 | Sync, onboarding |
| **L1** | `ocr_layer.py` | `gemini-3.1-flash-lite` | Abundant | 15/500 | Sync |
| **L2** | `profile_analyst.py` | `gemini-2.5-flash` | Scarce | 5/20 | Async, scheduled |
| **L3** | `generator.py`, `analyze_traps.py` | `gemini-3-flash-preview` | Scarce | 5/20 | Sync |
| **L4** | `critic.py` | `sarvam-105b` (fb: `gemini-3-flash-preview`) | Scarce | 5/20 | Sync |
| **CA** | `current_affairs.py` | `gemini-3.1-flash-lite` | Abundant | 15/500 | Scheduled daily |

## Guardrail — Two-Tier Design

**Tier 1 (Scarce — 2.5 Flash + 3 Flash):** 5 RPM / 20 RPD shared pool
- L0 Diagnostic, L2 Coach, L3 Engine, L4 Critic
- Budget split: 16 calls reserved for student actions / test gen / answer verify
- 4 calls reserved for PDF batch analysis (pauses if budget low)

**Tier 2 (Abundant — 3.1 Flash Lite):** 15 RPM / 500 RPD independent
- L1 OCR, CA Parser
- Effectively uncapped for daily usage

## Key Design Decisions

1. **Single student** — `student_id = "default"`. No auth.
2. **Diagnostic is one-time** — 60 questions (25 PYQ + 35 fresh with CA), 1-hour timer, all-at-once submission. Gate lifts permanently after completion.
3. **Existing data migration** — existing DB rows get `diagnostic_completed = True` on first startup.
4. **PDF pipeline is background, rate-limited** — runs in queue. If scarce tier budget < 5 remaining, PDF queue pauses.
5. **No migration script** — `init_db()` creates new tables if absent. New columns added via startup check.
6. **PYQ pool is static** — not rotating since diagnostic is one-time per student.
7. **API budget priority:** Student actions > PDF batch analysis > scheduled tasks.

---

## Phase 0 — Foundation

### 0.1 `backend/model_config.py` (NEW)

Per-layer model mapping. Each call goes through two-tier guardrail.

### 0.2 `.env` — Update

Replace old `GEMINI_MODEL` / `GEMINI_PROFILE_MODEL` with per-layer vars:
`DIAGNOSTIC_MODEL`, `OCR_MODEL`, `COACH_MODEL`, `ENGINE_MODEL`, `CRITIC_MODEL`, `CA_MODEL`

Add: `SARVAM_API_KEY`, `NEWS_SOURCES`

### 0.3 `api_guardrail.py` — Refactor

Split into two-tier guardrail. `execute_protected_gemini_call()` accepts optional `tier` param (default: "scarce").

### 0.4 `database.py` — Add CA DB

Add `current_affairs.db` connection + `SessionLocalCA`.

### 0.5 `models.py` — Add Tables

New tables: `diagnostic_questions`, `diagnostic_results`, `profile_analysis`, `question_topics`, `current_affairs` (in separate DB).
Extend `StudentProfile`: `diagnostic_completed`, `last_diagnostic_at`, `per_subject_accuracy`.

### 0.6 `requirements.txt` — Add

`feedparser`, `newspaper3k`, `schedule`

---

## Phase 1 — Layer 0: Diagnostic

### 1.1 `backend/diagnostic.py` (NEW)

- `build_diagnostic_bank(db)` — init: select 25 PYQs from `question_analysis`, store in `diagnostic_questions`
- `get_diagnostic_set(student_id, db)` — return 25 PYQs + 35 fresh from 3 Flash (with CA context)
- `grade_diagnostic(student_id, responses, db)` — score, compute ELO, per-subject accuracy, trap stats, populate profile

### 1.2 `main.py` — Endpoints + Gate

- `GET /diagnostic` — return 60 questions (no answers), start 1-hour timer
- `POST /diagnostic/submit` — accept all 60 responses, grade, create profile
- Gate middleware: all endpoints except `/diagnostic*`, `/health` return 403 if `diagnostic_completed != True`

### 1.3 Timer

Server-side timestamp check on submit — reject if >1 hour elapsed since `GET /diagnostic`.

---

## Phase 2 — Build Modules (Parallel)

### 2.1 CA Parser — `current_affairs.py` (NEW)

Model: 3.1 Flash Lite (abundant tier)
- RSS fetch → article extraction → Gemini parse → store
- Scheduler: runs at startup if >24hr since last fetch
- 6 endpoints in main.py

### 2.2 OCR Layer — `ocr_layer.py` (NEW)

Model: 3.1 Flash Lite (abundant tier)
- `read_omr_sheet(image_bytes, total)` → dict
- `extract_mains_answer(image_bytes)` → text

### 2.3 Coach — `profile_analyst.py` (NEW)

Model: 2.5 Flash (scarce tier)
- Topic classification → accuracy breakdown → error patterns → coach report
- Only runs with sufficient data (~50+ attempts)
- Triggered manually or scheduled

### 2.4 Critic — `critic.py` (NEW)

Model: Sarvam 105B (fallback: 3 Flash, scarce tier)
- Per-question quality checks → verdict (pass/review/fail)
- Max 2 regeneration retries on fail

---

## Phase 3 — Wire Integrations

### 3.1 `generator.py`

- Before: inject CA context from `current_affairs.get_relevant_entries()`
- After: pass through critic if `quality_check=True`

### 3.2 `analyze_traps.py`

- Pass `tier="scarce"` to guardrail call

### 3.3 `main.py` — OMR swap

- Replace inline Gemini vision with `ocr_layer.read_omr_sheet()`

---

## Phase 4 — Verification

4.1 Diagnostic flow — bank build, submit, grade, profile creation, gate
4.2 PDF pipeline — upload, analyze with 3 Flash, verify trap quality
4.3 CA module — fetch, list, detail, stats
4.4 OMR — upload image, verify bubble reading
4.5 Test generation — generate with CA + critic, verify output
4.6 Coach — trigger after sufficient data, verify report quality
4.7 Health check — confirm all layers report correct models

---

## File Summary

**New (6):**
- `backend/model_config.py`
- `backend/diagnostic.py`
- `backend/ocr_layer.py`
- `backend/profile_analyst.py`
- `backend/critic.py`
- `backend/current_affairs.py`

**Modified (7):**
- `backend/.env`
- `backend/api_guardrail.py`
- `backend/database.py`
- `backend/models.py`
- `backend/main.py`
- `backend/generator.py`
- `backend/analyze_traps.py`
