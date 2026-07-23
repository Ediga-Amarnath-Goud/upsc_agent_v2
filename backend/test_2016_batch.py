"""Run full pipeline on 2016 PDF: extract + single batch Gemini call."""
import sys, os
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.chdir(str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
load_dotenv()

from database import SessionLocal, DATA_DIR
from models import QuestionAnalysis, ActivityLog
from extract_questions import extract_questions
from analyze_traps import analyze_pdf_questions
from build_trap_summary import build_trap_summary


def main():
    db = SessionLocal()
    try:
        pdf_name = "Prelims_GS_Paper_1_2016_efbf12c724.pdf"
        md_path = DATA_DIR / "markdown" / "Prelims_GS_Paper_1_2016_efbf12c724.md"
        md_text = md_path.read_text(encoding="utf-8")

        questions = extract_questions(md_text)
        print(f"Extracted {len(questions)} questions from 2016 PDF")

        log = ActivityLog(
            source_pdf=pdf_name,
            stage="analyzing",
            progress=f"0/{len(questions)}",
            status="in_progress",
        )
        db.add(log)
        db.commit()
        db.refresh(log)

        analyze_pdf_questions(pdf_name, questions, db, log, len(questions))

        log.stage = "complete"
        log.status = "complete"
        log.completed_at = datetime.utcnow()
        db.commit()

        build_trap_summary(db)
        print("Trap summary rebuilt.")

        # Verify
        total = db.query(QuestionAnalysis).count()
        empty = db.query(QuestionAnalysis).filter(QuestionAnalysis.correct_key == "").count()
        print(f"DB: {total} questions, {empty} empty keys")
    finally:
        db.close()


if __name__ == "__main__":
    main()
