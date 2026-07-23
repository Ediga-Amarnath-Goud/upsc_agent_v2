import os
import re
import json
import uuid
import threading
from pathlib import Path
from datetime import datetime, timedelta, date
from dotenv import load_dotenv
from fastapi import FastAPI, Request, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

import logger
log = logger.get_logger("main")

from database import DATA_DIR, SessionLocal, get_session, get_ca_session, init_db
from models import ActivityLog, StudentProfile, TestSession, AttemptHistory, DiagnosticResults, DiagnosticQuestions, CuratedCA
from schemas import (
    TestRequest, SubmitAnswerPayload, SubmitAnswerResponse,
    GenerateTestResponse, ActivityLogResponse, StudentProfileResponse,
    OMRSubmitResponse, OMRQuestionResult, DiagnosticSubmitPayload,
    ProfileCreatePayload, ProfileStatusResponse,
    CuratedCAResponse, CuratedCAListResponse,
)
import math_utils


load_dotenv()

app = FastAPI(title="UPSC Agent V2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Diagnostic Gate Middleware ──────────────────────────────────────────────


@app.middleware("http")
async def onboarding_gate(request: Request, call_next):
    path = request.url.path
    open_paths = ("/health", "/profile/create", "/profile/status", "/profile",
                  "/docs", "/openapi.json")
    if path.startswith("/diagnostic") or path.startswith("/current-affairs") or path in open_paths:
        return await call_next(request)
    db = SessionLocal()
    try:
        student = db.query(StudentProfile).filter_by(student_id="default").first()
        if not student:
            return JSONResponse(
                status_code=403,
                content={"error": "Register first", "redirect": "/splash"},
            )
        if not student.diagnostic_completed:
            return JSONResponse(
                status_code=403,
                content={"error": "Complete diagnostic first", "redirect": "/consent"},
            )
    finally:
        db.close()
    return await call_next(request)


# ── Subject Mapping ──────────────────────────────────────────────────────────


SUBJECT_MAP = {
    "ancient": "History", "medieval": "History", "modern": "History",
    "history": "History",
    "polity": "Polity", "constitution": "Polity",
    "economy": "Economy", "economics": "Economy",
    "geography": "Geography", "geo": "Geography",
    "environment": "Environment", "ecology": "Environment",
    "science": "Science", "tech": "Science",
    "art": "Culture", "culture": "Culture",
}


def map_topic_to_subject(topic: str) -> str:
    t = topic.lower()
    for kw, subj in SUBJECT_MAP.items():
        if kw in t:
            return subj
    return "GS"


def get_student(db) -> StudentProfile:
    s = db.query(StudentProfile).filter_by(student_id="default").first()
    if not s:
        raise HTTPException(404, "No profile found. POST /profile/create to register.")
    return s


# ── Background Pipeline ─────────────────────────────────────────────────


def process_pdf_pipeline(pdf_path: str, log_id: int):
    db = SessionLocal()
    try:
        log = db.query(ActivityLog).filter_by(log_id=log_id).first()

        log.stage = "llamaparse"
        db.commit()
        from pdf_to_md import convert_pdf_to_markdown, MARKDOWN_DIR
        md_text = convert_pdf_to_markdown(pdf_path)

        from current_affairs import clean_pyq_markdown
        cleaned_md = clean_pyq_markdown(md_text)
        if cleaned_md != md_text:
            md_text = cleaned_md
            from pathlib import Path
            src = Path(pdf_path)
            md_path = MARKDOWN_DIR / f"{src.stem}.md"
            md_path.write_text(md_text, encoding="utf-8")

        log.stage = "extracting"
        db.commit()
        from extract_questions import extract_questions
        questions = extract_questions(md_text)

        log.stage = "analyzing"
        total = len(questions)
        log.progress = f"0/{total}"
        db.commit()

        # Load answer key if year detected in filename
        answer_key = None
        import re as _re
        m = _re.search(r"(20\d{2})", os.path.basename(pdf_path))
        if m:
            year = int(m.group(1))
            key_path = DATA_DIR / "answer_keys" / f"{year}.json"
            if key_path.exists():
                with open(key_path) as f:
                    answer_key = {int(k): v.upper() for k, v in json.load(f).items()}
                print(f"  Loaded answer key for {year} ({len(answer_key)} answers)")

        from analyze_traps import analyze_pdf_questions
        analyze_pdf_questions(os.path.basename(pdf_path), questions, db, log, total, answer_key=answer_key)

        from build_trap_summary import build_trap_summary
        build_trap_summary(db)

        # Pipeline A: classify PYQ CA sub-topics, then rebuild CA summary
        try:
            from models import DiagnosticQuestions
            has_pyqs = db.query(DiagnosticQuestions).filter_by(source="pyq", is_active=True).count() > 0
            if has_pyqs:
                from ca_summary import classify_pyq_ca_topics, update_summary_with_pyqs
                classify_pyq_ca_topics(db)
                update_summary_with_pyqs(db)
                print("  CA Pipeline A: summary rebuilt after PYQ analysis")
            else:
                print("  CA Pipeline A: no PYQ data, skipping")
        except Exception as exc:
            print(f"  CA Pipeline A failed: {exc}")

        log.stage = "complete"
        log.status = "complete"
        log.completed_at = datetime.utcnow()
        db.commit()
    except Exception as e:
        try:
            log = db.query(ActivityLog).filter_by(log_id=log_id).first()
            if log:
                log.status = "failed"
                log.error = str(e)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


# ── Startup ─────────────────────────────────────────────────────────────


@app.on_event("startup")
def startup():
    init_db()
    db = SessionLocal()
    student = db.query(StudentProfile).filter_by(student_id="default").first()
    if student and student.total_attempted > 0 and not student.diagnostic_completed:
        student.diagnostic_completed = True
        db.commit()
    db.close()

    # Build diagnostic PYQ bank if needed, then classify CA sub-topics and rebuild summary
    # Run in background thread so server starts immediately even if Gemini is slow/down
    def _startup_pipeline():
        ddb = SessionLocal()
        try:
            from diagnostic import build_diagnostic_bank
            build_diagnostic_bank(ddb)
            from models import DiagnosticQuestions
            has_pyqs = ddb.query(DiagnosticQuestions).filter_by(source="pyq", is_active=True).count() > 0
            if has_pyqs:
                from ca_summary import classify_pyq_ca_topics, update_summary_with_pyqs
                classify_pyq_ca_topics(ddb)
                update_summary_with_pyqs(ddb)
            else:
                print("  Startup: no PYQ data, skipping Pipeline A", flush=True)
        finally:
            ddb.close()

    threading.Thread(target=_startup_pipeline, daemon=True).start()

    # Start curated CA pipeline at 6:00 AM IST daily
    def _seconds_until_6am_ist():
        now = datetime.utcnow()
        target = now.replace(hour=0, minute=30, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        return int((target - now).total_seconds())

    def _curated_ca_scheduler():
        from current_affairs import curated_fetch_and_store

        def _first_run():
            print(f"  Curated CA: Running daily fetch at {datetime.utcnow().isoformat()} UTC")
            try:
                curated_fetch_and_store()
            except Exception as exc:
                print(f"  Curated CA fetch failed: {exc}")

            from current_affairs import generate_curated_digest_pdf
            try:
                from database import SessionLocalCA
                db = SessionLocalCA()
                generate_curated_digest_pdf(str(DATA_DIR / "pdfs" / f"curated_digest_{date.today()}.pdf"), db)
                db.close()
            except Exception as exc:
                print(f"  Curated CA digest failed: {exc}")

            # Rebuild CA_Summary weekly (check sentinel)
            from pathlib import Path
            summary_sentinel = DATA_DIR / "ca_summary_build_date.txt"
            should_rebuild = True
            if summary_sentinel.exists():
                try:
                    last_build = summary_sentinel.read_text().strip()
                    if last_build == str(date.today()):
                        should_rebuild = False
                except Exception:
                    pass
            if should_rebuild:
                try:
                    from models import DiagnosticQuestions
                    from database import SessionLocal
                    sdb = SessionLocal()
                    has_pyqs = sdb.query(DiagnosticQuestions).filter_by(source="pyq", is_active=True).count() > 0
                    if has_pyqs:
                        from ca_summary import classify_pyq_ca_topics, update_summary_with_pyqs
                        classify_pyq_ca_topics(sdb)
                        update_summary_with_pyqs(sdb)
                        print(f"  CA_Summary rebuilt")
                    else:
                        print(f"  CA_Summary rebuild skipped: no PYQ data")
                    sdb.close()
                    summary_sentinel.write_text(str(date.today()))
                except Exception as exc:
                    print(f"  CA_Summary rebuild failed: {exc}")

            threading.Timer(86400, _first_run).start()

        initial_delay = _seconds_until_6am_ist()
        print(f"  Curated CA: First run in {initial_delay}s (at 6 AM IST)")
        threading.Timer(initial_delay, _first_run).start()

    threading.Thread(target=_curated_ca_scheduler, daemon=True).start()


# ── Endpoints ───────────────────────────────────────────────────────────


@app.get("/health")
def health():
    return {}


@app.get("/images/ca/{entry_id}")
def serve_ca_image(entry_id: int):
    from database import SessionLocalCA
    from models import CuratedCA
    from fastapi.responses import FileResponse, RedirectResponse, Response
    import os
    db = SessionLocalCA()
    try:
        entry = db.query(CuratedCA).filter(CuratedCA.id == entry_id).first()
        if not entry:
            return Response("Not found", status_code=404)
        # Try local file
        img_dir = DATA_DIR / "ca_images"
        for ext in ("jpg", "jpeg", "png", "webp"):
            path = img_dir / f"{entry_id}.{ext}"
            if path.exists():
                return FileResponse(str(path))
        # Fallback proxy for external URLs
        if entry.image_url and entry.image_url.startswith("http"):
            return RedirectResponse(url=entry.image_url)
        # Fallback for images field (diagram descriptions — not served)
        return Response("Not found", status_code=404)
    finally:
        db.close()


# ── Current Affairs Endpoints ────────────────────────────────────────────────


@app.get("/current-affairs")
def list_current_affairs(
    category: str = None,
    relevance: str = None,
    search: str = None,
    date_from: str = None,
    date_to: str = None,
    date_fetched: str = None,
    source: str = None,
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_ca_session),
):
    from models import CurrentAffairs
    q = db.query(CurrentAffairs)
    if category:
        q = q.filter(CurrentAffairs.category == category)
    if relevance:
        q = q.filter(CurrentAffairs.upsc_relevance == relevance)
    if source:
        q = q.filter(CurrentAffairs.source == source)
    if search:
        q = q.filter(
            CurrentAffairs.title.ilike(f"%{search}%") |
            CurrentAffairs.summary.ilike(f"%{search}%")
        )
    if date_from:
        q = q.filter(CurrentAffairs.date_of_event >= date_from)
    if date_to:
        q = q.filter(CurrentAffairs.date_of_event <= date_to)
    if date_fetched:
        q = q.filter(CurrentAffairs.date_fetched == date_fetched)
    total = q.count()
    q = q.order_by(CurrentAffairs.created_at.desc())
    q = q.offset((page - 1) * per_page).limit(per_page)
    entries = q.all()
    results = []
    for e in entries:
        results.append({
            "id": e.id,
            "title": e.title,
            "summary": e.summary,
            "category": e.category,
            "subject": e.subject,
            "tags": json.loads(e.tags) if e.tags else [],
            "key_facts": json.loads(e.key_facts) if e.key_facts else [],
            "upsc_relevance": e.upsc_relevance,
            "source": e.source,
            "date_of_event": e.date_of_event,
            "date_fetched": e.date_fetched,
        })
    return {"total": total, "page": page, "per_page": per_page, "entries": results}


# Fixed-path CA routes MUST come before parameterized {entry_id} routes


@app.post("/current-affairs/fetch")
def trigger_ca_fetch():
    import threading
    from current_affairs import curated_fetch_and_store
    threading.Thread(target=curated_fetch_and_store, daemon=True).start()
    return {"status": "started", "message": "Curated fetch started in background"}


@app.post("/current-affairs/ingest")
def ingest_current_affairs(url: str = None, text: str = None, db: Session = Depends(get_ca_session)):
    if not url and not text:
        raise HTTPException(400, "Provide url or text")
    from current_affairs import _parse_article, _download_image
    from models import CurrentAffairs

    content = text or ""
    source = "manual"

    if url:
        try:
            import newspaper
            article = newspaper.Article(url)
            article.download()
            article.parse()
            content = article.text
            source = "manual"
        except Exception as e:
            raise HTTPException(400, f"Cannot fetch URL: {e}")

    parsed = _parse_article(url or "Manual Entry", content, url or "", source)
    entry = CurrentAffairs(
        title=parsed.get("title", "Manual Entry"),
        source=source,
        source_url=url or "",
        full_text=content,
        summary=parsed.get("summary", content[:300]),
        category=parsed.get("category", "General"),
        subject=parsed.get("subject", "GS"),
        tags=json.dumps(parsed.get("tags", [])),
        key_facts=json.dumps(parsed.get("key_facts", [])),
        historical_context=parsed.get("historical_context", ""),
        upsc_relevance=parsed.get("upsc_relevance", "medium"),
        date_of_event=parsed.get("date_of_event"),
        date_fetched=str(datetime.utcnow().date()),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    if url and entry.image_url:
        _download_image(entry.image_url, entry.id)
    return {"id": entry.id, "status": "stored"}


@app.post("/current-affairs/upload-pdf")
def upload_ca_pdf(file: UploadFile = File(...), db: Session = Depends(get_ca_session)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted")
    raw = file.file.read()
    if len(raw) > 50 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 50 MB)")
    pdf_dir = DATA_DIR / "uploads"
    pdf_dir.mkdir(exist_ok=True)
    dest = pdf_dir / f"ca_{uuid.uuid4().hex[:12]}_{file.filename}"
    dest.write_bytes(raw)
    import threading
    from current_affairs import ingest_ca_pdf

    def _run_analysis(reformatted_md):
        try:
            from ca_summary import update_summary_with_academy
            update_summary_with_academy(reformatted_md)
            print("  CA Pipeline B: summary rebuilt after academy PDF")
        except Exception as exc:
            print(f"  CA Pipeline B rebuild failed: {exc}")

    def _ingest_then_summarize(path):
        count, articles = ingest_ca_pdf(path)
        if articles:
            parts = [f"# {a['title']}\n\n{a['full_text']}" for a in articles]
            reformatted = "\n\n---\n\n".join(parts)
            threading.Thread(
                target=lambda: _run_analysis(reformatted),
                daemon=True
            ).start()

    threading.Thread(target=_ingest_then_summarize, args=(str(dest),), daemon=True).start()
    return {"status": "processing", "filename": file.filename}


@app.get("/current-affairs/stats")
def ca_stats(db: Session = Depends(get_ca_session)):
    from models import CurrentAffairs
    from sqlalchemy import func
    by_category = db.query(CurrentAffairs.category, func.count()).group_by(CurrentAffairs.category).all()
    by_relevance = db.query(CurrentAffairs.upsc_relevance, func.count()).group_by(CurrentAffairs.upsc_relevance).all()
    total = db.query(CurrentAffairs).count()
    today = db.query(CurrentAffairs).filter(
        CurrentAffairs.date_fetched == str(datetime.utcnow().date())
    ).count()
    return {
        "total": total,
        "today": today,
        "by_category": dict(by_category),
        "by_relevance": dict(by_relevance),
    }


@app.get("/current-affairs/digest/pdf")
def download_ca_digest(db: Session = Depends(get_ca_session)):
    pdf_dir = DATA_DIR / "pdfs"
    pdf_dir.mkdir(exist_ok=True)
    pdf_path = str(pdf_dir / f"ca_digest_{datetime.utcnow().date()}.pdf")
    from current_affairs import generate_digest_pdf
    generate_digest_pdf(pdf_path, db)
    if not Path(pdf_path).exists():
        raise HTTPException(500, "Digest generation failed")
    return FileResponse(pdf_path, media_type="application/pdf", filename=Path(pdf_path).name)


# Parameterized {entry_id} routes (must come after all fixed paths)


@app.get("/current-affairs/{entry_id}")
def get_current_affairs(entry_id: int, db: Session = Depends(get_ca_session)):
    from models import CurrentAffairs
    e = db.query(CurrentAffairs).filter_by(id=entry_id).first()
    if not e:
        raise HTTPException(404, "Entry not found")
    return {
        "id": e.id,
        "title": e.title,
        "summary": e.summary,
        "historical_context": e.historical_context,
        "category": e.category,
        "subject": e.subject,
        "tags": json.loads(e.tags) if e.tags else [],
        "key_facts": json.loads(e.key_facts) if e.key_facts else [],
        "upsc_relevance": e.upsc_relevance,
        "image_url": e.image_url,
        "source": e.source,
        "source_url": e.source_url,
        "date_of_event": e.date_of_event,
    }


@app.get("/current-affairs/{entry_id}/pdf")
def download_ca_pdf(entry_id: int, db: Session = Depends(get_ca_session)):
    from models import CurrentAffairs
    e = db.query(CurrentAffairs).filter_by(id=entry_id).first()
    if not e:
        raise HTTPException(404, "Entry not found")
    pdf_dir = DATA_DIR / "pdfs"
    pdf_dir.mkdir(exist_ok=True)
    from current_affairs import generate_digest_pdf
    pdf_path = str(pdf_dir / f"ca_{entry_id}.pdf")
    generate_digest_pdf(pdf_path, db)
    if not Path(pdf_path).exists():
        raise HTTPException(500, "PDF generation failed")
    import re
    title_slug = re.sub(r'[^a-zA-Z0-9]+', '_', (e.title or f"ca_{entry_id}")[:50]).strip('_').lower()
    filename = f"ca_{e.category or 'general'}_{title_slug}.pdf"
    return FileResponse(pdf_path, media_type="application/pdf", filename=filename)


# ── Curated CA Endpoints ────────────────────────────────────────────────────


@app.get("/curated-ca", response_model=CuratedCAListResponse)
def list_curated_ca(
    category: str = None,
    gs_linkage: str = None,
    date_fetched: str = None,
    priority: str = None,
    source: str = None,
    source_not: str = None,
    search: str = None,
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_ca_session),
):
    q = db.query(CuratedCA)
    if category:
        q = q.filter(CuratedCA.category == category)
    if gs_linkage:
        q = q.filter(CuratedCA.gs_linkage == gs_linkage)
    if date_fetched:
        q = q.filter(CuratedCA.date_fetched == date_fetched)
    if priority:
        q = q.filter(CuratedCA.priority == priority)
    if source:
        sources = source.split(",")
        q = q.filter(CuratedCA.source.in_(sources))
    if source_not:
        excludes = source_not.split(",")
        q = q.filter(~CuratedCA.source.in_(excludes))
    if search:
        like = f"%{search}%"
        q = q.filter(CuratedCA.title.ilike(like) | CuratedCA.summary.ilike(like))
    total = q.count()
    items = q.order_by(CuratedCA.date_fetched.desc(), CuratedCA.id.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "items": [_curated_ca_to_dict(e) for e in items],
    }


def _curated_ca_to_dict(e: CuratedCA) -> dict:
    return {
        "id": e.id,
        "issue_id": e.issue_id,
        "title": e.title,
        "source_url": e.source_url,
        "source": e.source,
        "summary": e.summary,
        "category": e.category,
        "gs_linkage": e.gs_linkage,
        "tags": json.loads(e.tags) if e.tags else [],
        "supporting_arguments": json.loads(e.supporting_arguments) if e.supporting_arguments else [],
        "counter_arguments": json.loads(e.counter_arguments) if e.counter_arguments else [],
        "way_forward": json.loads(e.way_forward) if e.way_forward else [],
        "prelims_high_yield_facts": json.loads(e.prelims_high_yield_facts) if e.prelims_high_yield_facts else [],
        "matched_via": e.matched_via,
        "matched_micro_topic": e.matched_micro_topic,
        "is_academy_verified": e.is_academy_verified,
        "is_supplemental": e.is_supplemental,
        "predicted_traps": json.loads(e.predicted_traps) if e.predicted_traps else None,
        "image_url": e.image_url,
        "priority": e.priority or "medium",
        "newspaper_name": e.newspaper_name,
        "date_of_event": e.date_of_event,
        "date_fetched": e.date_fetched,
    }


@app.get("/curated-ca/{entry_id}", response_model=CuratedCAResponse)
def get_curated_ca(entry_id: int, db: Session = Depends(get_ca_session)):
    e = db.query(CuratedCA).filter_by(id=entry_id).first()
    if not e:
        raise HTTPException(404, "Curated CA entry not found")
    return _curated_ca_to_dict(e)


@app.patch("/curated-ca/{entry_id}")
def patch_curated_ca(entry_id: int, body: dict, db: Session = Depends(get_ca_session)):
    e = db.query(CuratedCA).filter_by(id=entry_id).first()
    if not e:
        raise HTTPException(404, "Curated CA entry not found")
    if "priority" in body:
        if body["priority"] not in ("high", "medium", "low"):
            raise HTTPException(400, "priority must be 'high', 'medium', or 'low'")
        e.priority = body["priority"]
    db.commit()
    return _curated_ca_to_dict(e)


# ── Diagnostic Endpoints ────────────────────────────────────────────────────


@app.get("/diagnostic")
def start_diagnostic(db: Session = Depends(get_session)):
    # Don't require profile — profile is created at submit time
    # Use "pending" as temporary student_id (SQLite doesn't enforce FK)
    try:
        from diagnostic import generate_diagnostic_set
        session_id, qp_path, ak_path = generate_diagnostic_set("pending", db)
    except RuntimeError as e:
        raise HTTPException(429, str(e))
    except Exception as e:
        raise HTTPException(503, f"Generation failed: {str(e)}")

    # Fetch stored questions for CBT rendering
    dr = db.query(DiagnosticResults).filter_by(session_id=session_id).first()
    questions = []
    if dr:
        qs = db.query(DiagnosticQuestions).filter(
            DiagnosticQuestions.id.in_(dr.question_ids)
        ).all()
        q_map = {q.id: q for q in qs}
        for i, qid in enumerate(dr.question_ids):
            q = q_map.get(qid)
            if q:
                questions.append({
                    "index": i,
                    "question_text": q.question_text,
                    "options": q.options,
                    "difficulty_tier": q.difficulty_tier,
                })

    return {
        "session_id": session_id,
        "total": len(questions) or 60,
        "time_limit_seconds": 3600,
        "question_paper_url": f"/diagnostic/question-paper?session_id={session_id}",
        "questions": questions,
    }


@app.get("/diagnostic/question-paper")
def download_diagnostic_qp(session_id: str, db: Session = Depends(get_session)):
    dr = db.query(DiagnosticResults).filter_by(session_id=session_id).first()
    if not dr or not dr.pdf_path or not Path(dr.pdf_path).exists():
        raise HTTPException(404, "Question paper not found")
    return FileResponse(dr.pdf_path, media_type="application/pdf", filename=Path(dr.pdf_path).name)


@app.post("/diagnostic/submit")
def submit_diagnostic(body: DiagnosticSubmitPayload, db: Session = Depends(get_session)):
    # Create profile on first diagnostic submit
    student = db.query(StudentProfile).filter_by(student_id="default").first()
    if not student:
        if not body.name or not body.age or not body.gender:
            raise HTTPException(400, "Profile data (name, age, gender) required for first submission")
        student = StudentProfile(
            student_id="default",
            name=body.name,
            age=body.age,
            gender=body.gender,
            current_elo=1200,
            onboarding_complete=True,
        )
        db.add(student)
        db.commit()
        db.refresh(student)

    if student.diagnostic_completed:
        raise HTTPException(400, "Diagnostic already completed")

    dr = db.query(DiagnosticResults).filter_by(
        session_id=body.session_id, student_id="pending"
    ).first()
    if not dr:
        raise HTTPException(404, "Diagnostic session not found")
    if dr.responses:
        raise HTTPException(400, "Diagnostic already submitted")

    # Link session to real profile
    dr.student_id = "default"
    db.flush()

    # Enforce 1-hour timer
    if dr.started_at:
        elapsed = (datetime.utcnow() - dr.started_at).total_seconds()
        if elapsed > 3600:
            raise HTTPException(400, "Time limit exceeded (1 hour)")

    import diagnostic as dx
    dx.grade_diagnostic("default", body.session_id, body.responses, db)
    return {"status": "completed", "message": "Diagnostic submitted successfully"}


@app.get("/diagnostic/answer-key")
def download_diagnostic_ak(session_id: str, db: Session = Depends(get_session)):
    dr = db.query(DiagnosticResults).filter_by(session_id=session_id).first()
    if not dr or not dr.answer_key_path or not Path(dr.answer_key_path).exists():
        raise HTTPException(404, "Answer key not found")
    return FileResponse(dr.answer_key_path, media_type="application/pdf", filename=Path(dr.answer_key_path).name)


# ── PDF Upload Pipeline ────────────────────────────────────────────────────


@app.post("/upload-pdf")
def upload_pdf(
    file: UploadFile = File(...),
    subject_code: str = Form(None),
    db: Session = Depends(get_session),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted")
    raw = file.file.read()
    if len(raw) > 50 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 50 MB)")
    dest = DATA_DIR / "uploads" / file.filename
    dest.write_bytes(raw)
    log = ActivityLog(source_pdf=file.filename, stage="uploaded")
    db.add(log)
    db.commit()
    db.refresh(log)
    threading.Thread(
        target=process_pdf_pipeline, args=(str(dest), log.log_id), daemon=True
    ).start()
    return {"log_id": log.log_id}


@app.get("/activity-log")
def list_activity_logs(db: Session = Depends(get_session)):
    logs = db.query(ActivityLog).order_by(ActivityLog.started_at.desc()).all()
    return [
        ActivityLogResponse(
            log_id=l.log_id,
            source_pdf=l.source_pdf,
            stage=l.stage,
            progress=l.progress,
            status=l.status,
            started_at=l.started_at.isoformat(),
        )
        for l in logs
    ]


@app.get("/activity-log/{log_id}")
def get_activity_log(log_id: int, db: Session = Depends(get_session)):
    log = db.query(ActivityLog).filter_by(log_id=log_id).first()
    if not log:
        raise HTTPException(404, "Activity log not found")
    return ActivityLogResponse(
        log_id=log.log_id,
        source_pdf=log.source_pdf,
        stage=log.stage,
        progress=log.progress,
        status=log.status,
        started_at=log.started_at.isoformat(),
    )


@app.get("/trap-summary")
def trap_summary():
    p = DATA_DIR / "trap_summary.json"
    if not p.exists():
        raise HTTPException(404, "No trap summary yet – analyse a PDF first")
    return JSONResponse(content=json.loads(p.read_text("utf-8")))


@app.post("/generate-test/prelims", response_model=GenerateTestResponse)
def generate_test(body: TestRequest, db: Session = Depends(get_session)):
    topic = body.topic_studied.strip()
    if not topic:
        raise HTTPException(400, "topic_studied cannot be empty")
    count = max(1, min(30, body.question_count))
    subject = map_topic_to_subject(topic)
    student = get_student(db)
    quality_check = getattr(body, "quality_check", True)

    try:
        from generator import generate_test_content
        questions, answer_key = generate_test_content(
            topic, subject, count, student, db, quality_check=quality_check
        )
    except RuntimeError as e:
        raise HTTPException(429, str(e))
    except Exception as e:
        log.error("generate_test_content failed: %s", e)
        raise HTTPException(500, f"Generation failed: {e}")

    session_id = str(uuid.uuid4())
    short_id = session_id[:8]
    today_str = datetime.utcnow().strftime("%Y%m%d")
    topic_slug = re.sub(r'[^a-zA-Z0-9]+', '_', topic.lower()).strip('_')[:30]
    pdf_name = f"practice_{topic_slug}_{today_str}_{short_id}.pdf"
    pdf_path = str(DATA_DIR / "pdfs" / pdf_name)

    try:
        from pdf_generator import generate_question_pdf, generate_answer_key_pdf
        question_dicts = [q.model_dump() for q in questions]
        generate_question_pdf(question_dicts, topic, pdf_path, session_id=session_id)
        ak_pdf_name = pdf_name.replace(".pdf", "_answer_key.pdf")
        ak_pdf_path = str(DATA_DIR / "pdfs" / ak_pdf_name)
        generate_answer_key_pdf([k.model_dump() for k in answer_key], ak_pdf_path, session_id=session_id)
    except Exception as e:
        log.error("PDF generation failed: %s", e)
        # Return response without PDF URL so the user isn't stuck
        return GenerateTestResponse(
            session_id=session_id,
            total_questions=len(questions),
            pdf_url=None,
            time_limit_seconds=1800,
        )

    try:
        session = TestSession(
            session_id=session_id,
            subject_code=subject,
            topic_studied=topic,
            questions=question_dicts,
            answer_key=[k.model_dump() for k in answer_key],
            pdf_path=pdf_path,
            answer_key_path=ak_pdf_path,
            status="in_progress",
        )
        db.add(session)
        db.commit()
    except Exception as e:
        log.error("DB save failed: %s", e)
        # PDF was generated; still return the session so the user can test
        return GenerateTestResponse(
            session_id=session_id,
            total_questions=len(questions),
            pdf_url=f"/session/{session_id}/question-paper",
            time_limit_seconds=1800,
        )

    return GenerateTestResponse(
        session_id=session_id,
        total_questions=len(questions),
        pdf_url=f"/session/{session_id}/question-paper",
        time_limit_seconds=1800,
    )


@app.get("/session/{session_id}/data")
def session_data(session_id: str, db: Session = Depends(get_session)):
    session = db.query(TestSession).filter_by(session_id=session_id).first()
    if not session:
        raise HTTPException(404, "Session not found")
    return {
        "session_id": session.session_id,
        "subject_code": session.subject_code,
        "topic_studied": session.topic_studied,
        "questions": session.questions,
        "responses": session.responses or {},
        "score": session.score,
        "status": session.status,
    }


@app.get("/session/{session_id}/question-paper")
def download_question_paper(session_id: str, db: Session = Depends(get_session)):
    session = db.query(TestSession).filter_by(session_id=session_id).first()
    if not session:
        raise HTTPException(404, "Session not found")
    if not session.pdf_path or not Path(session.pdf_path).exists():
        raise HTTPException(404, "Question paper PDF not found")
    return FileResponse(
        session.pdf_path,
        media_type="application/pdf",
        filename=Path(session.pdf_path).name,
    )


@app.get("/session/{session_id}/answer-key")
def download_answer_key(session_id: str, db: Session = Depends(get_session)):
    session = db.query(TestSession).filter_by(session_id=session_id).first()
    if not session:
        raise HTTPException(404, "Session not found")
    if not session.answer_key_path or not Path(session.answer_key_path).exists():
        raise HTTPException(404, "Answer key PDF not found")
    return FileResponse(
        session.answer_key_path,
        media_type="application/pdf",
        filename=Path(session.answer_key_path).name,
    )


@app.post("/submit-answer", response_model=SubmitAnswerResponse)
def submit_answer(body: SubmitAnswerPayload, db: Session = Depends(get_session)):
    session = db.query(TestSession).filter_by(session_id=body.session_id).first()
    if not session:
        raise HTTPException(404, "Session not found")
    if session.status == "completed":
        raise HTTPException(400, "Session already completed")

    answer_key = session.answer_key
    idx = body.question_index
    if idx < 0 or idx >= len(answer_key):
        raise HTTPException(400, f"question_index out of range (0–{len(answer_key)-1})")

    responses = session.responses or {}
    if str(idx) in responses:
        raise HTTPException(400, "Duplicate answer for this question")

    resp = body.response.upper().strip()
    if resp not in ("A", "B", "C", "D"):
        raise HTTPException(400, "response must be A, B, C, or D")

    entry = answer_key[idx]
    correct = resp == entry["correct_answer"]

    student = get_student(db)
    difficulty = entry.get("difficulty_tier", 5)
    new_elo, delta = math_utils.compute_elo_update(
        student.current_elo, difficulty, correct, student.total_attempted
    )
    student.current_elo = new_elo
    student.total_attempted += 1
    if correct:
        student.total_correct += 1

    trap_type = entry.get("trap_type", "general")
    student.trap_stats = math_utils.update_trap_stats(
        student.trap_stats or {}, trap_type, correct
    )
    subject = session.subject_code or "GENERAL"
    student.subject_trap_accuracy = math_utils.update_subject_trap_accuracy(
        student.subject_trap_accuracy or {}, subject, trap_type, correct
    )
    student.last_active = datetime.utcnow()

    attempt = AttemptHistory(
        session_id=body.session_id,
        question_index=idx,
        response=resp,
        correct=correct,
        time_taken=body.time_taken,
        trap_type=trap_type,
    )
    db.add(attempt)

    responses[str(idx)] = resp
    session.responses = responses

    correct_count = 0
    for qs, ans in responses.items():
        qi = int(qs)
        if qi < len(answer_key) and ans == answer_key[qi]["correct_answer"]:
            correct_count += 1
    session.score = correct_count

    if len(responses) >= len(answer_key):
        session.status = "completed"

    db.commit()
    db.refresh(session)

    return SubmitAnswerResponse(
        correct=correct,
        correct_answer=entry["correct_answer"],
        trap_explanation=entry.get("trap_explanation", ""),
        most_likely_wrong_reason=entry.get("most_likely_wrong_reason", ""),
        score=session.score,
        elo_delta=delta,
    )


@app.post("/submit-omr", response_model=OMRSubmitResponse)
def submit_omr(
    session_id: str = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_session),
):
    session = db.query(TestSession).filter_by(session_id=session_id).first()
    if not session:
        raise HTTPException(404, "Session not found")
    if session.status == "completed":
        raise HTTPException(400, "Session already completed")

    answer_key = session.answer_key
    img_bytes = image.file.read()

    try:
        from ocr_layer import read_omr_sheet
        omr_result = read_omr_sheet(img_bytes, len(answer_key))
        omr_responses = {}
        for idx, ans in omr_result.items():
            if ans is not None:
                omr_responses[str(idx)] = ans
    except RuntimeError as e:
        raise HTTPException(429, str(e))

    if not omr_responses:
        raise HTTPException(400, "Could not read any bubbles from OMR image")

    student = get_student(db)
    results = []
    total_elo_delta = 0
    existing = session.responses or {}

    for idx_str, resp_letter in omr_responses.items():
        idx = int(idx_str)
        if idx < 0 or idx >= len(answer_key):
            continue
        if idx_str in existing:
            continue

        entry = answer_key[idx]
        correct = resp_letter == entry["correct_answer"]
        difficulty = entry.get("difficulty_tier", 5)

        new_elo, delta = math_utils.compute_elo_update(
            student.current_elo, difficulty, correct, student.total_attempted,
        )
        student.current_elo = new_elo
        student.total_attempted += 1
        if correct:
            student.total_correct += 1

        trap_type = entry.get("trap_type", "general")
        student.trap_stats = math_utils.update_trap_stats(
            student.trap_stats or {}, trap_type, correct,
        )
        subject = session.subject_code or "GENERAL"
        student.subject_trap_accuracy = math_utils.update_subject_trap_accuracy(
            student.subject_trap_accuracy or {}, subject, trap_type, correct,
        )

        attempt = AttemptHistory(
            session_id=session_id,
            question_index=idx,
            response=resp_letter,
            correct=correct,
            trap_type=trap_type,
        )
        db.add(attempt)

        existing[idx_str] = resp_letter
        total_elo_delta += delta

        results.append(OMRQuestionResult(
            question_index=idx,
            response=resp_letter,
            correct=correct,
            correct_answer=entry["correct_answer"],
            trap_explanation=entry.get("trap_explanation", ""),
            most_likely_wrong_reason=entry.get("most_likely_wrong_reason", ""),
        ))

    student.last_active = datetime.utcnow()
    session.responses = existing
    session.score = sum(
        1 for r in results if r.correct
    )
    session.status = "completed"
    db.commit()

    return OMRSubmitResponse(
        session_id=session_id,
        total_questions=len(answer_key),
        answered_count=len(results),
        correct_count=session.score,
        score=session.score,
        elo_delta=total_elo_delta,
        results=results,
    )


@app.post("/ocr/mains-evaluate")
def ocr_mains_evaluate(image: UploadFile = File(...)):
    from ocr_layer import extract_mains_answer
    img_bytes = image.file.read()
    result = extract_mains_answer(img_bytes)
    return result


@app.get("/tests")
def list_tests(db: Session = Depends(get_session)):
    practice = db.query(TestSession).order_by(TestSession.started_at.desc()).all()
    diagnostic = db.query(DiagnosticResults).order_by(DiagnosticResults.started_at.desc()).all()
    result = []
    for s in practice:
        result.append({
            "type": "practice",
            "session_id": s.session_id,
            "topic": s.topic_studied,
            "date": (s.started_at.isoformat() if s.started_at else ""),
            "score": s.score,
            "total": len(s.questions) if s.questions else 0,
            "status": s.status or "generated",
            "pdf_available": bool(s.pdf_path) if hasattr(s, "pdf_path") else True,
            "ak_available": bool(s.answer_key_path),
        })
    for d in diagnostic:
        result.append({
            "type": "diagnostic",
            "session_id": d.session_id,
            "topic": "Diagnostic Test",
            "date": (d.started_at.isoformat() if d.started_at else ""),
            "score": d.score,
            "total": d.total,
            "status": "completed" if d.responses else "pending",
            "pdf_available": bool(d.pdf_path),
            "ak_available": bool(d.answer_key_path),
        })
    result.sort(key=lambda x: x["date"], reverse=True)
    today_str = str(datetime.utcnow().date())
    ca_count = 0
    try:
        from models import CurrentAffairs
        from database import SessionLocalCA
        ca_db = SessionLocalCA()
        try:
            ca_count = ca_db.query(CurrentAffairs).filter(
                CurrentAffairs.date_fetched == today_str
            ).count()
        finally:
            ca_db.close()
    except Exception:
        pass
    return {
        "tests": result,
        "ca_digests": [
            {
                "date": today_str,
                "article_count": ca_count,
                "pdf_url": "/current-affairs/digest/pdf",
            }
        ],
    }


@app.post("/profile/create")
def create_profile(body: ProfileCreatePayload, db: Session = Depends(get_session)):
    existing = db.query(StudentProfile).filter_by(student_id="default").first()
    if existing:
        raise HTTPException(400, "Profile already exists")
    s = StudentProfile(
        student_id="default",
        name=body.name,
        age=body.age,
        gender=body.gender,
        current_elo=1200,
        onboarding_complete=True,
    )
    db.add(s)
    db.commit()
    return {"status": "created", "name": body.name}


@app.get("/profile/status", response_model=ProfileStatusResponse)
def profile_status(db: Session = Depends(get_session)):
    s = db.query(StudentProfile).filter_by(student_id="default").first()
    return ProfileStatusResponse(
        registered=s is not None,
        diagnostic_completed=s.diagnostic_completed if s else False,
        name=s.name if s else None,
    )


@app.get("/profile", response_model=StudentProfileResponse)
def student_profile(db: Session = Depends(get_session)):
    student = get_student(db)
    acc = round(student.total_correct / student.total_attempted, 4) if student.total_attempted > 0 else 0.0
    return StudentProfileResponse(
        name=student.name,
        age=student.age,
        gender=student.gender,
        diagnostic_completed=student.diagnostic_completed,
        onboarding_complete=student.onboarding_complete,
        current_elo=student.current_elo,
        subject_elos=student.subject_elos or {},
        total_attempted=student.total_attempted,
        total_correct=student.total_correct,
        accuracy=acc,
    )


@app.post("/analyze-profile")
def trigger_profile_analysis(db: Session = Depends(get_session)):
    from profile_analyst import run_analysis
    student = get_student(db)
    result = run_analysis(student.student_id)
    if result.get("status") == "skipped":
        return result
    return {"status": "started", "message": "Profile analysis queued"}


@app.get("/profile/analysis")
def get_profile_analysis(db: Session = Depends(get_session)):
    student = get_student(db)
    analysis = db.query(ProfileAnalysis).filter_by(
        student_id=student.student_id
    ).order_by(ProfileAnalysis.created_at.desc()).first()
    if not analysis:
        raise HTTPException(404, "No profile analysis yet. POST /analyze-profile to generate one.")
    return {
        "structured_data": json.loads(analysis.structured_data) if analysis.structured_data else {},
        "coach_report": analysis.coach_report,
        "created_at": analysis.created_at.isoformat(),
    }
