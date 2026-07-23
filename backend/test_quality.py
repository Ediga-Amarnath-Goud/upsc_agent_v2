"""Quality check: show first 10 questions from each file."""
import sys
sys.path.insert(0, str(__file__).rsplit('\\', 1)[0])

from pathlib import Path
from extract_questions import extract_questions

data_dir = Path(__file__).resolve().parent / "data" / "markdown"
for md_path in sorted(data_dir.glob("*.md")):
    text = md_path.read_text(encoding="utf-8")
    if not text.strip():
        continue
    qs = extract_questions(text)
    print(f"\n{'='*60}")
    print(f"{md_path.name}: {len(qs)} questions")
    print(f"{'='*60}")
    for i, q in enumerate(qs[:10]):
        ql = q["question_text"][:120].replace("\n", " ")
        print(f"  [{i+1}] {ql}")
        print(f"       A:{q['options']['A'][:50]} | B:{q['options']['B'][:50]} | C:{q['options']['C'][:50]} | D:{q['options']['D'][:50]}")
    if len(qs) > 10:
        print(f"  ... and {len(qs)-10} more")
