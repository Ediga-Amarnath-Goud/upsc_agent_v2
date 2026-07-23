"""Count real English vs garbled questions per file."""
import sys, re
sys.path.insert(0, str(__file__).rsplit('\\', 1)[0])

from pathlib import Path
from extract_questions import extract_questions

def is_english_q(text):
    """Heuristic: real English question starts with capital word, has many letters, few non-ASCII."""
    if not text:
        return False
    text = text.strip()
    # Must start with uppercase letter (not digit, not symbol)
    if not text or not text[0].isupper():
        return False
    # At least 20 chars
    if len(text) < 20:
        return False
    # High alpha ratio
    alpha = sum(1 for c in text if c.isalpha())
    if alpha / max(len(text), 1) < 0.4:
        return False
    # Majority of chars should be ASCII
    ascii_count = sum(1 for c in text if ord(c) < 128)
    if ascii_count / max(len(text), 1) < 0.7:
        return False
    return True

data_dir = Path(__file__).resolve().parent / "data" / "markdown"
for md_path in sorted(data_dir.glob("*.md")):
    text = md_path.read_text(encoding="utf-8")
    if not text.strip():
        continue
    qs = extract_questions(text)
    english = [q for q in qs if is_english_q(q["question_text"])]
    garbled = [q for q in qs if not is_english_q(q["question_text"])]
    print(f"{md_path.name}: {len(english)} English / {len(garbled)} garbled (total {len(qs)})")
    if garbled:
        for g in garbled[:3]:
            safe = g["question_text"][:100].encode("ascii", "ignore").decode()
            print(f"   GARBLED: {safe}")
