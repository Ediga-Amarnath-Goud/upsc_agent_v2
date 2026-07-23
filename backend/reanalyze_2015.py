"""Re-analyze only 2015 questions — delete old 2015 rows and re-run analysis."""
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.chdir(str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
load_dotenv()

from database import SessionLocal, DATA_DIR
from models import QuestionAnalysis, ActivityLog
from extract_questions import extract_questions
from analyze_traps import analyze_pdf_questions
from verify_answers import fetch_answer_key
from build_trap_summary import build_trap_summary
from datetime import datetime

db = SessionLocal()
try:
    # Delete old 2015 rows
    deleted = db.query(QuestionAnalysis).filter(QuestionAnalysis.source_pdf.contains("2015")).delete()
    db.commit()
    print(f"Deleted {deleted} old 2015 rows")

    # Re-extract from markdown
    md_path = DATA_DIR / "markdown" / "Prelims_GS_Paper_1_2015_c32006c6bc.md"
    md_text = md_path.read_text(encoding="utf-8")
    questions = extract_questions(md_text)
    print(f"Extracted {len(questions)} questions")

    answer_key = fetch_answer_key(2015)

    log = ActivityLog(
        source_pdf="Prelims_GS_Paper_1_2015_c32006c6bc.pdf",
        stage="reanalyzing",
        progress=f"0/{len(questions)}",
        status="in_progress",
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    analyze_pdf_questions(
        "Prelims_GS_Paper_1_2015_c32006c6bc.pdf",
        questions, db, log, len(questions),
        answer_key=answer_key,
    )

    log.stage = "complete"
    log.status = "complete"
    log.completed_at = datetime.utcnow()
    db.commit()

    build_trap_summary(db)
    print("Done. Trap summary rebuilt.")
finally:
    db.close()
