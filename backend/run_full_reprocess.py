"""Full reprocess: wipe DB, extract all 3 years, Gemini batch with official answer keys, rebuild."""
import sys
import os
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
load_dotenv()

# Provider selection: "deepseek" (default) or "gemini"
PROVIDER = os.environ.get("ANALYSIS_PROVIDER", "deepseek").lower()

from database import SessionLocal, DATA_DIR, init_db
from models import ActivityLog
from extract_questions import extract_questions
from analyze_traps import analyze_pdf_questions
from verify_answers import fetch_answer_key
from build_trap_summary import build_trap_summary


def _guess_year(filename: str) -> int | None:
    for y in range(2010, 2030):
        if str(y) in filename:
            return y
    return None


def cleanup_old_scripts():
    for f in sorted(Path(__file__).resolve().parent.glob("reprocess*.py")):
        if f.name != "run_full_reprocess.py":
            f.unlink()
            print(f"  Deleted {f.name}")


def main():
    db_path = DATA_DIR / "upsc_agent.db"
    if db_path.exists():
        db_path.unlink()
        print("Deleted old database")
    init_db()
    print("Database recreated")

    db = SessionLocal()
    try:
        markdown_dir = DATA_DIR / "markdown"
        total_questions = 0

        for md_path in sorted(markdown_dir.glob("*.md")):
            if md_path.stat().st_size == 0:
                print(f"\nSkipping {md_path.name} (empty)")
                continue

            pdf_name = md_path.with_suffix(".pdf").name
            md_text = md_path.read_text(encoding="utf-8")
            questions = extract_questions(md_text)

            if not questions:
                print(f"\n{md_path.name}: 0 questions — skipping")
                continue

            print(f"\n{md_path.name}: {len(questions)} questions extracted")
            total_questions += len(questions)

            # Fetch official answer key for this year
            year = _guess_year(pdf_name)
            answer_key = fetch_answer_key(year) if year else {}

            log = ActivityLog(
                source_pdf=pdf_name,
                stage="analyzing",
                progress=f"0/{len(questions)}",
                status="in_progress",
            )
            db.add(log)
            db.commit()
            db.refresh(log)

            # For DeepSeek accuracy benchmark, pass answer_key=None for raw accuracy
            # For production with injection, pass answer_key for correct answers
            use_injection = os.environ.get("INJECT_ANSWER_KEY", "1") == "1"
            ak = answer_key if (use_injection and answer_key) else None

            analyze_pdf_questions(
                pdf_name, questions, db, log, len(questions),
                answer_key=ak,
                provider=PROVIDER,
            )

            log.stage = "complete"
            log.status = "complete"
            db.commit()
            print(f"  Analyzed: {len(questions)} questions")

        print(f"\n{'='*50}")
        print(f"Total questions across all years: {total_questions}")
        print(f"{'='*50}")

        build_trap_summary(db)

        print("\n--- Cleanup ---")
        cleanup_old_scripts()

        print("\nDone! Full reprocess complete.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
