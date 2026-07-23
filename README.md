# UPSC Agent v2

AI-powered UPSC civil services exam preparation assistant with diagnostic analysis, personalized coaching, current affairs curation, and test generation.

## Features

- **Diagnostic Engine** — Analyzes PYQ performance across subjects, identifies weak areas, and builds a personalized student profile
- **Adaptive Coaching** — 4-layer AI pipeline (Generator → Critic → Engine → Coach) generates tailored practice questions and explanations
- **Curated Current Affairs** — Multi-stage pipeline: RSS feed aggregation → LLM quality gate → batch enrichment → image-aware storage. Academy PDF ingestion with diagram extraction via Gemini.
- **Test Generation** — Generates full-length mock tests from PYQ patterns with answer key extraction and OMR evaluation
- **Tracker System** — Per-model API usage quotas with daily limits, retry logic with exponential backoff

## Tech Stack

- **Backend:** Python, FastAPI, SQLAlchemy, Google Gemini API
- **Frontend:** React + Vite, Tailwind CSS
- **Data:** SQLite, RSS Feeds, PDF parsing via Gemini

## Quick Start

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

Set environment variables in `.env` (see `.env.example` for required keys).
