# Batch 1 Blueprint — UPSC Agent V2

## System Purpose
Process UPSC Prelims PDFs into trap-indexed question structures, log student profiles using ELO ratings, and serve adaptive tests with API economy guardrails.

---

## Core File Architecture

```
upsc_agent_v2/
├── .env                       # GEMINI_API_KEY, GEMINI_MODEL, HOST, PORT
├── requirements.txt           # Shared dependencies (backend + frontend)
├── main.py                    # FastAPI — All endpoints
├── database.py                # SQLite engine, session, init_db()
├── models.py                  # 5 tables (SQLAlchemy)
├── schemas.py                 # Pydantic validation + native SDK JSON schemas
├── api_guardrail.py           # RPM + RPD sliding-window tracker
├── pdf_to_md.py               # Marker wrapper
├── extract_questions.py       # Markdown → structured questions
├── analyze_traps.py           # Per-question Gemini + checkpointing
├── build_trap_summary.py      # Aggregate DB → trap_summary.json
├── pyq_analyzer.py            # Query helper (topic, trap_type, performance)
├── generator.py               # Runtime quiz engine (answer_key hidden in DB)
├── pdf_generator.py           # fpdf2 — question paper PDF layout
├── math_utils.py              # ELO, decay
├── frontend/                  # UI (future)
└── data/
    ├── uploads/               # Source PDFs
    ├── markdown/              # .md files from Marker
    ├── pdfs/                  # Generated question paper PDFs
    ├── trap_summary.json      # Aggregated trap patterns
    └── api_usage_tracker.json # Guardrail daily counter
```

## Database Tables

### activity_log
| Column | Type | Notes |
|---|---|---|
| log_id | INTEGER PK | auto |
| source_pdf | TEXT | filename |
| stage | TEXT | marker → extracting → analyzing → complete |
| progress | TEXT | e.g. "47 / 100" |
| status | TEXT | in_progress / complete / failed |
| error | TEXT | null |
| started_at | DATETIME | |
| completed_at | DATETIME | null |

### question_analysis
| Column | Type |
|---|---|
| id | INTEGER PK |
| source_pdf | TEXT |
| question_text | TEXT |
| options | JSON |
| correct_key | TEXT(1) |
| trap_type | TEXT |
| trap_mechanism | TEXT |
| distraction_analysis | JSON |
| most_likely_wrong | TEXT(1) |
| most_likely_wrong_reason | TEXT |
| related_concepts | JSON |
| difficulty_tier | INTEGER |
| created_at | DATETIME |

### student_profile (single row — no student_id in requests)
| Column | Type | Default |
|---|---|---|
| student_id | TEXT PK | uuid |
| name | TEXT | "Student" |
| current_elo | INTEGER | 1200 |
| total_attempted | INTEGER | 0 |
| total_correct | INTEGER | 0 |
| trap_stats | JSON | {} |
| weakness_tags | JSON | [] |

### test_session
| Column | Type |
|---|---|
| session_id | TEXT PK |
| subject_code | TEXT |
| topic_studied | TEXT |
| questions | JSON |
| answer_key | JSON (hidden from client) |
| responses | JSON, default {} |
| score | INTEGER |
| status | TEXT |
| started_at | DATETIME |

### attempt_history
| Column | Type |
|---|---|
| attempt_id | INTEGER PK |
| session_id | TEXT FK |
| question_index | INTEGER |
| response | TEXT(1) |
| correct | BOOLEAN |
| time_taken | INTEGER |
| trap_type | TEXT |

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | /upload-pdf | Upload → Marker → extract → analyze → DB |
| GET | /activity-log | All analysis jobs |
| GET | /activity-log/{log_id} | Single job progress |
| GET | /trap-summary | Stream trap_summary.json |
| POST | /generate-test/prelims | Generate Qs → hide key → create PDF |
| GET | /session/{session_id}/question-paper | Download question PDF |
| POST | /submit-answer | Score + ELO + trap reveal (reject duplicates) |
| GET | /health | Status |

## Key Rules
- **Single student** — no student_id in requests
- **No mock AI** — guardrail blocks honestly when limit reached
- **No safe_mode.py** — removed entirely
- **Guardrail daily reset** — auto-creates `api_usage_tracker.json`
- **Duplicate answer check** — reject if question_index already in session.responses
- **PDF generation** — fpdf2 creates question paper (questions only, no answers)

## Model Strategy
| Environment | Model |
|---|---|
| Testing (free tier) | gemini-3.1-flash-lite |
| Production (paid) | gemini-3.5-flash |

Configured via GEMINI_MODEL in .env — one model per deployment.
