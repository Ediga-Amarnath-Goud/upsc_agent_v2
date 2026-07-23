import json
import time
import uuid
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from google.genai import types

from database import DATA_DIR
from models import DiagnosticQuestions, DiagnosticResults, StudentProfile
from api_guardrail import protected_gemini_call
import logger
log = logger.get_logger("diagnostic")

SUBJECT_KEYWORDS = {
    "Polity": ["fundamental rights", "directive principles", "constitution", "parliament", "supreme court",
               "governor", "president", "amendment", "judiciary", "election", "panchayat", "municipality",
               "article", "schedule", "federal", "union", "state", "citizen", "minister", "lok sabha",
               "rajya sabha", "bill", "act", "ordinance", "writ", "vote", "democracy", "secular"],
    "History": ["ancient", "medieval", "modern", "gupta", "maurya", "mughal", "sultanate", "british",
                "independence", "national movement", "gandhi", "nehru", "revolt", "sati", "vedic",
                "indus", "harappa", "ashoka", "chola", "vikramaditya", "akbar", "shah", "maratha",
                "battle", "treaty", "governor general", "viceroy", "partition", "constitutional"],
    "Economy": ["gdp", "gnp", "inflation", "fiscal", "monetary", "rbi", "budget", "five year", "niti",
                "tax", "gst", "subsidy", "poverty", "unemployment", "liberalization", "privatization",
                "globalization", "bank", "insurance", "sebi", "market", "trade", "export", "import",
                "agriculture", "food security", "msp", "public expenditure"],
    "Geography": ["monsoon", "climate", "river", "mountain", "soil", "vegetation", "latitude", "longitude",
                  "tropic", "equator", "hemisphere", "plateau", "plain", "desert", "glacier", "cyclone",
                  "earthquake", "volcano", "biosphere", "national park", "wildlife", "sanctuary",
                  "map", "location", "state", "district", "population", "migration", "urban"],
    "Environment": ["ecology", "ecosystem", "biodiversity", "endangered", "species", "forest", "coral",
                    "wetland", "climate change", "global warming", "pollution", "renewable", "carbon",
                    "greenhouse", "ozone", "conservation", "sustainable", "waste", "recycling"],
    "Science": ["dna", "rna", "protein", "cell", "virus", "bacteria", "vaccine", "satellite", "isro",
                "nasa", "quantum", "laser", "nuclear", "electron", "proton", "neutron", "gravity",
                "relativity", "genome", "biotech", "nanotech", "crispr", "ai", "ml", "robot"],
    "Culture": ["dance", "music", "festival", "temple", "sculpture", "painting", "literature", "poetry",
                "sanskrit", "veda", "upanishad", "purana", "epic", "ramayana", "mahabharata",
                "classical", "folk", "tribal", "handicraft", "architecture", "cave", "stupa"],
}


def _classify_subject(text: str) -> str:
    t = text.lower()
    scores = {}
    for subject, keywords in SUBJECT_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in t)
        if count > 0:
            scores[subject] = count
    if scores:
        return max(scores, key=scores.get)
    return "GS"


def build_diagnostic_bank(db: Session):
    """Select up to 25 PYQs from question_analysis and store in diagnostic_questions.
    Idempotent — skips if PYQ bank already exists."""
    existing = db.query(DiagnosticQuestions).filter_by(source="pyq", is_active=True).count()
    if existing >= 25:
        return

    from models import QuestionAnalysis
    rows = db.query(QuestionAnalysis).filter(
        QuestionAnalysis.trap_type.isnot(None),
        QuestionAnalysis.trap_type != "Corrupted Question",
        QuestionAnalysis.correct_key.isnot(None),
        QuestionAnalysis.correct_key != "",
    ).all()

    by_subject: dict[str, list] = {}
    for r in rows:
        subj = _classify_subject(r.question_text)
        by_subject.setdefault(subj, []).append(r)

    target_per_subject = {
        "Polity": 5, "History": 5, "Economy": 3, "Geography": 3,
        "Environment": 3, "Science": 3, "Culture": 3,
    }
    selected = []
    for subj, target in target_per_subject.items():
        pool = by_subject.get(subj, by_subject.get("GS", []))
        if not pool:
            pool = [r for r in rows if r not in selected]
        selected.extend(pool[:target])

    if len(selected) < 25:
        extras = [r for r in rows if r not in selected]
        selected.extend(extras[:25 - len(selected)])

    for r in selected[:25]:
        db.add(DiagnosticQuestions(
            question_text=r.question_text,
            options=r.options,
            correct_key=r.correct_key,
            subject=_classify_subject(r.question_text),
            difficulty_tier=r.difficulty_tier or 5,
            trap_type=r.trap_type,
            source="pyq",
            is_active=True,
        ))
    db.commit()


GENERATION_PROMPT = """\
You are a UPSC Prelims paper setter. Generate exactly 35 questions covering Polity, History, Economy, Geography, Environment, Science, and Culture at varying difficulty tiers (1-10).

Mix difficulty across the set. Include at least 8 questions on current/recent events from 2025-2026.

Each question must have exactly 4 options (A, B, C, D) with one clearly correct answer.

Return a JSON object with a single array "questions" where each element has:
- question_text (string)
- options (object with keys A/B/C/D)
- correct_key (A/B/C/D)
- subject (string: Polity/History/Economy/Geography/Environment/Science/Culture)
- difficulty_tier (integer 1-10)
- trap_type (short label e.g. "Factual Error", "Misleading Chronology", "Extreme Language", "False Association")
- trap_mechanism (1-2 sentence explanation of the trap)
- correct_explanation (1-2 sentences explaining why the correct answer is right)

Return ONLY valid JSON, no markdown fences."""


def _gemini_call(prompt: str) -> list[dict]:
    """Single Gemini API call. Returns parsed questions list or raises."""
    resp = protected_gemini_call("diagnostic", lambda c, m: c.models.generate_content(
        model=m,
        contents=prompt,
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(),
            max_output_tokens=65536,
        ),
    ))
    um = resp.usage_metadata
    if um:
        log.info("  tokens — prompt=%d output=%d total=%d",
                 um.prompt_token_count, um.candidates_token_count, um.total_token_count)

    if not resp.text or not resp.text.strip():
        raise ValueError("Empty response from Gemini")

    text = resp.text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0].strip()
    import re
    text = re.sub(r'[\x00-\x1f]', '', text)
    if not text:
        raise ValueError("Empty text after cleanup")
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as e:
        log.error("JSON parse failed: %s. Text: %s", e, text[:300])
        raise

    questions = raw.get("questions", [])
    if not questions:
        raise ValueError("No questions in response")
    return questions


def generate_diagnostic_set(student_id: str, db: Session) -> tuple[str, str, str]:
    """Generate diagnostic set: 25 PYQs + 35 fresh. Returns (session_id, pdf_path, ak_path)."""
    pyqs = db.query(DiagnosticQuestions).filter_by(source="pyq", is_active=True).limit(25).all()
    if len(pyqs) < 25:
        build_diagnostic_bank(db)
        pyqs = db.query(DiagnosticQuestions).filter_by(source="pyq", is_active=True).limit(25).all()

    log.info("Generating 35 diagnostic questions in one call...")
    t0 = time.time()
    all_generated = _gemini_call(GENERATION_PROMPT)[:35]
    log.info("Got %d questions in %.1fs", len(all_generated), time.time() - t0)

    if not all_generated:
        raise ValueError("No questions generated")

    # Deduplicate and validate
    seen_texts = []
    validated = []
    for gq in all_generated:
        opts = gq.get("options", {})
        opt_vals = [v for v in opts.values() if v]
        if len(set(opt_vals)) < 4:
            log.warning("Skipping question with duplicate/missing options: %.60s", gq.get("question_text", ""))
            continue
        txt = (gq.get("question_text") or "").strip()
        if not txt:
            log.warning("Skipping question with empty text")
            continue
        import difflib
        for prev in seen_texts:
            if difflib.SequenceMatcher(None, txt.lower(), prev.lower()).ratio() > 0.85:
                log.warning("Skipping near-duplicate question: %.60s", txt)
                break
        else:
            seen_texts.append(txt)
            validated.append(gq)
    all_generated = validated
    log.info("After dedup: %d questions", len(all_generated))

    if not all_generated:
        raise ValueError("All questions were filtered out")

    gen_ids = []
    for gq in all_generated:
        try:
            dq = DiagnosticQuestions(
                question_text=gq.get("question_text", ""),
                options=gq.get("options", {}),
                correct_key=gq.get("correct_key", ""),
                subject=gq.get("subject", _classify_subject(gq.get("question_text", ""))),
                difficulty_tier=gq.get("difficulty_tier", 5),
                trap_type=gq.get("trap_type"),
                ca_reference=gq.get("trap_mechanism", ""),
                source="generated",
                is_active=True,
            )
        except Exception as e:
            log.warning("Skipping malformed diagnostic question: %s", e)
            continue
        db.add(dq)
        db.flush()
        gen_ids.append(dq.id)
    db.commit()

    all_questions = list(pyqs) + db.query(DiagnosticQuestions).filter(
        DiagnosticQuestions.id.in_(gen_ids)
    ).all()

    import random
    random.shuffle(all_questions)

    question_ids = [q.id for q in all_questions]

    session_id = str(uuid.uuid4())

    # Persist the session→question mapping FIRST so CBT always works
    result = DiagnosticResults(
        student_id=student_id,
        session_id=session_id,
        question_ids=question_ids,
        score=0,
        total=len(all_questions),
        per_subject={},
        pdf_path="",
        answer_key_path="",
        started_at=datetime.utcnow(),
    )
    db.add(result)
    db.commit()

    # Build PDF content
    qp_content = []
    ak_content = []
    for idx, q in enumerate(all_questions):
        trap_data = None
        if q.source == "pyq":
            from models import QuestionAnalysis
            pq = db.query(QuestionAnalysis).filter(
                QuestionAnalysis.question_text == q.question_text
            ).first()
            if pq:
                trap_data = {
                    "trap_type": pq.trap_type,
                    "trap_mechanism": pq.trap_mechanism,
                    "correct_explanation": pq.trap_mechanism or "",
                }
        else:
            trap_data = {
                "trap_type": q.trap_type,
                "trap_mechanism": q.ca_reference,
                "correct_explanation": "",
            }
            # Trap data for generated questions is in the generation response
            for gq in all_generated:
                if gq.get("question_text") == q.question_text:
                    trap_data["trap_mechanism"] = gq.get("trap_mechanism", "")
                    trap_data["correct_explanation"] = gq.get("correct_explanation", "")
                    break

        qp_content.append({
            "question_text": q.question_text,
            "options": q.options,
            "difficulty_tier": q.difficulty_tier,
        })
        ak_content.append({
            "question_text": q.question_text,
            "options": q.options,
            "correct_key": q.correct_key,
            "subject": q.subject,
            "difficulty_tier": q.difficulty_tier,
            "trap_type": trap_data["trap_type"] if trap_data else "",
            "trap_mechanism": trap_data["trap_mechanism"] if trap_data else "",
            "correct_explanation": trap_data["correct_explanation"] if trap_data else "",
        })

    # Generate PDFs as a separate best-effort step
    pdf_dir = DATA_DIR / "diagnostic"
    pdf_dir.mkdir(exist_ok=True)

    today_str = datetime.utcnow().strftime("%Y%m%d")
    qp_path = str(pdf_dir / f"diagnostic_{today_str}_{session_id[:8]}_question_paper.pdf")
    ak_path = str(pdf_dir / f"diagnostic_{today_str}_{session_id[:8]}_answer_key.pdf")

    try:
        from pdf_generator import generate_question_pdf, generate_answer_key_pdf
        generate_question_pdf(qp_content, "UPSC Diagnostic Test", qp_path, session_id=session_id)
        generate_answer_key_pdf(ak_content, ak_path, session_id=session_id)
        result.pdf_path = qp_path
        result.answer_key_path = ak_path
        db.commit()
    except Exception as e:
        log.error("Diagnostic PDF generation failed (CBT still works): %s", e)

    return session_id, qp_path, ak_path


def grade_diagnostic(student_id: str, session_id: str, responses: dict[int, str], db: Session):
    """Grade the diagnostic, populate profile. No score returned to user."""
    dr = db.query(DiagnosticResults).filter_by(
        session_id=session_id, student_id=student_id
    ).first()
    if not dr:
        raise ValueError("Diagnostic session not found")
    if dr.responses:
        raise ValueError("Diagnostic already submitted")
    if dr.started_at and (datetime.utcnow() - dr.started_at).total_seconds() > 3600:
        raise ValueError("Time limit exceeded — 1 hour has passed since diagnostic started")

    questions = db.query(DiagnosticQuestions).filter(
        DiagnosticQuestions.id.in_(dr.question_ids)
    ).all()
    q_map = {q.id: q for q in questions}

    correct_count = 0
    per_subject = {}
    import math_utils

    student = db.query(StudentProfile).filter_by(student_id=student_id).first()

    for idx_str, answer in responses.items():
        idx = int(idx_str)
        if idx < 0 or idx >= len(dr.question_ids):
            continue
        qid = dr.question_ids[idx]
        q = q_map.get(qid)
        if not q:
            continue

        is_correct = answer.upper() == q.correct_key
        if is_correct:
            correct_count += 1

        subj = q.subject or "GS"
        per_subject.setdefault(subj, {"correct": 0, "total": 0})
        per_subject[subj]["total"] += 1
        if is_correct:
            per_subject[subj]["correct"] += 1

        if student:
            new_elo, _ = math_utils.compute_elo_update(
                student.current_elo or 1200, q.difficulty_tier or 5, is_correct, student.total_attempted or 0
            )
            student.current_elo = new_elo
            student.total_attempted = (student.total_attempted or 0) + 1
            if is_correct:
                student.total_correct = (student.total_correct or 0) + 1

            subj_elos = student.subject_elos or {}
            subj_elo = subj_elos.get(subj, 1200)
            new_subj_elo, _ = math_utils.compute_elo_update(
                subj_elo, q.difficulty_tier or 5, is_correct, per_subject[subj]["total"]
            )
            subj_elos[subj] = new_subj_elo
            student.subject_elos = subj_elos

            if q.trap_type:
                student.trap_stats = math_utils.update_trap_stats(
                    student.trap_stats or {}, q.trap_type, is_correct
                )

            student.diagnostic_completed = True
            student.last_diagnostic_at = datetime.now(timezone.utc)
            student.last_active = datetime.now(timezone.utc)

    if student:
        student.per_subject_accuracy = {
            subj: round(data["correct"] / data["total"], 4)
            for subj, data in per_subject.items()
        }

    dr.responses = responses
    dr.score = correct_count
    dr.per_subject = per_subject
    db.commit()
