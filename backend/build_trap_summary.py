import json
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path(__file__).resolve().parent / "data"


def build_trap_summary(db_session):
    from models import QuestionAnalysis

    rows = db_session.query(QuestionAnalysis).all()
    by_trap = defaultdict(list)

    for r in rows:
        by_trap.setdefault(r.trap_type or "unknown", []).append(
            {
                "id": r.id,
                "source_pdf": r.source_pdf,
                "question_text": r.question_text,
                "trap_mechanism": r.trap_mechanism,
                "most_likely_wrong": r.most_likely_wrong,
                "most_likely_wrong_reason": r.most_likely_wrong_reason,
                "difficulty_tier": r.difficulty_tier,
            }
        )

    summary = [
        {
            "trap_type": t,
            "count": len(items),
            "avg_difficulty": round(
                sum(it["difficulty_tier"] or 5 for it in items) / len(items), 1
            ),
            "examples": items[:5],
        }
        for t, items in sorted(by_trap.items(), key=lambda x: len(x[1]), reverse=True)
    ]

    path = DATA_DIR / "trap_summary.json"
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary
