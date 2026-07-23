"""Test extraction with safe encoding for terminal output."""
import sys, json
sys.path.insert(0, str(__file__).rsplit('\\', 1)[0])

from pathlib import Path
from extract_questions import extract_questions

data_dir = Path(__file__).resolve().parent / "data" / "markdown"
for md_path in sorted(data_dir.glob("*.md")):
    text = md_path.read_text(encoding="utf-8")
    if not text.strip():
        continue
    qs = extract_questions(text)
    english = [q for q in qs if q["question_text"].encode("ascii", "ignore").decode().strip()]
    safe_name = md_path.name.encode("ascii", "ignore").decode()
    print(f"{safe_name}: {len(qs)} total, {len(english)} ASCII-meaningful")
