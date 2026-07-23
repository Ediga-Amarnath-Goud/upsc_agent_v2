import json
import re
import os
from pathlib import Path
from dotenv import load_dotenv
from google.genai import types

load_dotenv()

DATA_DIR = Path(__file__).resolve().parent / "data" / "answer_keys"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _parse_key_text(text: str) -> dict[int, str]:
    answers = {}
    for m in re.finditer(r"(\d{1,3})\s*[.:)\s]+\s*([A-D])\b", text):
        num = int(m.group(1))
        ans = m.group(2).upper()
        if 1 <= num <= 100 and ans in "ABCD":
            answers[num] = ans
    return answers


def _fetch_key_via_gemini(year: int) -> dict[int, str] | None:
    try:
        from api_guardrail import protected_gemini_call

        prompt = (
            f"Provide the official UPSC Civil Services Prelims {year} "
            f"General Studies Paper 1 answer key. "
            f"Return a JSON object where keys are question numbers (1-100 as integers) "
            f"and values are the correct answer letters (A, B, C, or D). "
            f"Example: {{\"1\": \"A\", \"2\": \"C\", ...}}\n\n"
            f"Use the OFFICIAL UPSC answer key. Return ONLY valid JSON."
        )
        resp = protected_gemini_call("critic", lambda c, m: c.models.generate_content(
            model=m,
            contents=prompt,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(),
                max_output_tokens=65536,
            ),
        ))
        data = json.loads(resp.text)
        if isinstance(data, dict):
            result = {}
            for k, v in data.items():
                try:
                    num = int(k)
                    if 1 <= num <= 100 and v.upper() in "ABCD":
                        result[num] = v.upper()
                except (ValueError, AttributeError):
                    pass
            if len(result) >= 90:
                return result
    except Exception as e:
        print(f"  Gemini fetch failed: {e}")
    return None


def fetch_answer_key(year: int) -> dict[int, str]:
    cache_path = DATA_DIR / f"{year}.json"
    if cache_path.exists():
        raw = json.loads(cache_path.read_text(encoding="utf-8"))
        return {int(k): v for k, v in raw.items()}

    print(f"  Fetching answer key for {year}...")
    result = _fetch_key_via_gemini(year)

    if result and len(result) >= 90:
        cache_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        print(f"  Saved answer key for {year} ({len(result)} answers)")
        return result

    print(f"  WARNING: Could not fetch complete answer key for {year}")
    return {}


def verify_questions(db_session):
    from models import QuestionAnalysis

    # Ensure DB columns exist (migration for SQLite)
    from sqlalchemy import inspect, text
    from database import engine

    inspector = inspect(engine)
    cols = [c["name"] for c in inspector.get_columns("question_analysis")]
    with engine.begin() as conn:
        if "verified_answer" not in cols:
            conn.execute(text("ALTER TABLE question_analysis ADD COLUMN verified_answer VARCHAR(1)"))
            print("  Added column: verified_answer")
        if "gemini_correct" not in cols:
            conn.execute(text("ALTER TABLE question_analysis ADD COLUMN gemini_correct BOOLEAN"))
            print("  Added column: gemini_correct")
        if "question_number" not in cols:
            conn.execute(text("ALTER TABLE question_analysis ADD COLUMN question_number INTEGER"))
            print("  Added column: question_number")

    rows = db_session.query(QuestionAnalysis).all()
    if not rows:
        print("  No questions to verify")
        return

    # Group by year extracted from filename convention
    by_year = {}
    for r in rows:
        for y in range(2010, 2030):
            if str(y) in (r.source_pdf or ""):
                by_year.setdefault(y, []).append(r)
                break

    total_verified = 0
    total_gemini_correct = 0

    for year, year_rows in sorted(by_year.items()):
        key = fetch_answer_key(year)
        if not key:
            print(f"  Skipping {year} — no answer key available")
            continue

        year_correct = 0
        for r in year_rows:
            qnum = r.question_number
            if qnum is None or qnum not in key:
                print(f"  Warning: q#{r.id} has question_number={qnum}, key has {len(key)} entries")
                continue
            official = key[qnum]
            r.verified_answer = official
            r.gemini_correct = (r.correct_key == official)
            if r.gemini_correct:
                year_correct += 1
            total_verified += 1

        db_session.commit()
        pct = round(100 * year_correct / len(year_rows), 1) if year_rows else 0
        total_gemini_correct += year_correct
        print(f"  {year}: {year_correct}/{len(year_rows)} = {pct}% Gemini matches UPSC key")

    if total_verified:
        overall = round(100 * total_gemini_correct / total_verified, 1)
        print(f"\n  Overall: {total_gemini_correct}/{total_verified} = {overall}% Gemini accuracy")
    else:
        print("\n  No questions verified")
