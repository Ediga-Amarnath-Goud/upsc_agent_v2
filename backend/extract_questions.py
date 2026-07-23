import re
import json

HEADER_BLOCK_RE = re.compile(
    r"(?:^|\n\n)#{1,2}\s*(\d+)\s*[.)]\s*(.*?)(?=\n\n#{1,2}\s*\d+\s*[.)]|\Z)",
    re.DOTALL,
)

PLAIN_BLOCK_RE = re.compile(
    r"(?:^|\n\n)(\d+)\s*[.)]\s*(.*?)(?=\n\n(?:\d+\s*[.)])|\Z)",
    re.DOTALL,
)

DASH_OPTION_RE = re.compile(
    r"^\s*-?\s*\(?([A-Da-d])\)?\s*(.*?)$",
    re.MULTILINE,
)

TABLE_OPTION_RE = re.compile(
    r"^\|\s*\(([A-Da-d])\)\s*\|\s*(.*?)\s*\|",
    re.MULTILINE,
)


def _extract_options(block: str):
    opt_matches = list(DASH_OPTION_RE.finditer(block))
    for j in range(len(opt_matches) - 3):
        keys = [opt_matches[j + k].group(1).upper() for k in range(4)]
        if keys == ["A", "B", "C", "D"]:
            return {keys[k]: opt_matches[j + k].group(2).strip() for k in range(4)}, opt_matches[j].start()

    table_matches = list(TABLE_OPTION_RE.finditer(block))
    for j in range(len(table_matches) - 3):
        keys = [table_matches[j + k].group(1).upper() for k in range(4)]
        if keys == ["A", "B", "C", "D"]:
            return {keys[k]: table_matches[j + k].group(2).strip() for k in range(4)}, table_matches[j].start()

    return None, None


def extract_questions(markdown_text: str) -> list[dict]:
    questions = []
    found_numbers = set()

    # Pass 1: extract from # N. headings (reliable)
    for m in HEADER_BLOCK_RE.finditer(markdown_text):
        num = int(m.group(1))
        block = m.group(2).strip()
        if not block:
            continue
        options, opt_text_pos = _extract_options(block)
        if not options:
            options, opt_text_pos = _extract_options(m.group(0))
        if options:
            question_text = block[:opt_text_pos].strip() if opt_text_pos else block
            questions.append({
                "question_number": num,
                "question_text": question_text,
                "options": options,
            })
            found_numbers.add(num)

    # Pass 2: fill gaps with plain N. blocks that have valid options
    for m in PLAIN_BLOCK_RE.finditer(markdown_text):
        num = int(m.group(1))
        if num in found_numbers:
            continue
        block = m.group(2).strip()
        if not block:
            continue
        options, opt_text_pos = _extract_options(block)
        if not options:
            options, opt_text_pos = _extract_options(m.group(0))
        if options:
            question_text = block[:opt_text_pos].strip() if opt_text_pos else block
            questions.append({
                "question_number": num,
                "question_text": question_text,
                "options": options,
            })
            found_numbers.add(num)

    # Deduplicate: keep first occurrence of each question_number
    seen = set()
    deduped = []
    for q in questions:
        qn = q.get("question_number")
        if qn and qn in seen:
            continue
        if qn is None:
            continue
        seen.add(qn)
        deduped.append(q)

    # Filter to valid range 1-100
    questions = [q for q in deduped if 1 <= q.get("question_number", 0) <= 100]
    questions.sort(key=lambda q: q["question_number"])

    if not questions:
        questions = _fallback_gemini_parse(markdown_text)

    return questions


def _fallback_gemini_parse(markdown_text: str) -> list[dict]:
    from api_guardrail import protected_gemini_call
    from google.genai import types

    prompt = (
        "You are parsing a UPSC Civil Services Prelims question paper. "
        "Extract ALL questions from the following markdown text. "
        "Each element must have: question_text (string), options (object with A/B/C/D keys), "
        "question_number (int), "
        "correct_key (single uppercase letter A-D -- use your knowledge of UPSC PYQs "
        "to determine the correct answer).\n\n"
        "Return ONLY valid JSON, no markdown fences.\n\n"
        f"{markdown_text}"
    )

    try:
        resp = protected_gemini_call("engine", lambda c, m: c.models.generate_content(
            model=m,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        ))
        data = json.loads(resp.text)
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []
