"""Test the new extraction regex on existing markdown files without touching DB."""
import sys
sys.path.insert(0, str(__file__).rsplit('\\', 1)[0])

from pathlib import Path
from extract_questions import extract_questions

data_dir = Path(__file__).resolve().parent / "data" / "markdown"
for md_path in sorted(data_dir.glob("*.md")):
    text = md_path.read_text(encoding="utf-8")
    print(f"\n{'='*60}")
    print(f"File: {md_path.name} ({len(text)} chars)")
    print(f"{'='*60}")
    if not text.strip():
        print("  SKIP — empty file")
        continue
    qs = extract_questions(text)
    print(f"  Extracted: {len(qs)} questions")
    for i, q in enumerate(qs[:5]):
        print(f"  [{i+1}] {q['question_text'][:100]}...")
        print(f"       Options: {list(q['options'].keys())} -> {list(q['options'].values())}")
    if len(qs) > 5:
        print(f"  ... and {len(qs)-5} more")
