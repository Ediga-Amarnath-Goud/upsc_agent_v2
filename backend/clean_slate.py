"""Clear all existing data for the fresh batch test."""
import sys, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.chdir(str(Path(__file__).resolve().parent))

from database import SessionLocal, DATA_DIR
from models import QuestionAnalysis, ActivityLog


def main():
    db = SessionLocal()
    try:
        n_q = db.query(QuestionAnalysis).delete()
        n_l = db.query(ActivityLog).delete()
        db.commit()
        print(f"Cleared {n_q} question_analysis rows, {n_l} activity_log rows")

        trap_path = DATA_DIR / "trap_summary.json"
        if trap_path.exists():
            trap_path.unlink()
            print("Deleted trap_summary.json")

        tracker_path = DATA_DIR / "api_usage_tracker.json"
        if tracker_path.exists():
            import json
            tracker_path.write_text(json.dumps({"date": "2026-06-13", "count": 0}))
            print("Reset api_usage_tracker to 0")

    finally:
        db.close()


if __name__ == "__main__":
    main()
