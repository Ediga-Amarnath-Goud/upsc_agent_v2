import json
import re
import time
from pathlib import Path
from api_guardrail import protected_gemini_call
from deepseek_api import call_deepseek_batch
from google.genai import types

DATA_DIR = Path(__file__).resolve().parent / "data"

BATCH_SIZE = 20

GEMINI_PROMPT_HEADER = """\
You are a UPSC exam strategist. Analyse the following Prelims questions and identify the trap structure for EACH question. The correct answer is provided and is authoritative.

For each question:
1. Read the question and all four options carefully.
2. Accept the given correct answer as final. Do NOT question it.
3. Focus on the THREE WRONG options — identify how each is designed to trap students.
4. Assign a consistent trap_type label describing the DISTRACTORS' trap pattern.

CRITICAL LABEL RULES:
- "Corrupted Question" means the text is UNREADABLE (garbled characters, encoding errors). Do NOT use it for readable questions.
- "Factual Error" means the WRONG options contain factual errors. The correct answer is NOT an error.
- Reuse EXACT labels. Keep total label count small (~5-15 for a batch of 50). Only create a new label if the trap pattern is genuinely different from all existing ones.

Return a JSON ARRAY of results, one per question in the SAME ORDER as listed below. Each result object must have:
- correct_key: which option is correct (A/B/C/D)
- trap_type: short label (e.g. "Factual Error", "Misleading Chronology", "Extreme Language", "False Association", "Scope Creep", "Partial Truth", "Qualifier Trap")
- trap_mechanism: 1-2 sentence explanation of how the trap works
- distraction_analysis: object with keys A-D, each value is why that option is wrong (or empty string for the correct answer)
- most_likely_wrong: which wrong option is most tempting (A/B/C/D)
- most_likely_wrong_reason: why that option lures students
- related_concepts: list of concept keywords
- difficulty_tier: integer 1 (easiest) to 10 (hardest)

Return ONLY valid JSON array, no markdown fences.

"""

GEMINI_PROMPT_HEADER_SOLVE = """\
You are a UPSC exam strategist. Solve the following Prelims questions step by step.

For EACH question:
1. Read the question and all four options carefully.
2. Evaluate A, B, C, D independently - reason why each is right or wrong.
3. Determine the correct answer using your knowledge.
4. Explain the trap - how wrong options tempt students.
5. Assign a consistent trap_type label.

CRITICAL LABEL RULES:
- "Corrupted Question" means the text is UNREADABLE (garbled characters, encoding errors). Do NOT use it for readable questions.
- "Factual Error" means the WRONG options contain factual errors. The correct answer is NOT an error.
- Reuse EXACT labels. Keep total label count small (~5-15 for a batch of 50). Only create a new label if the trap pattern is genuinely different from all existing ones.
- Think through each question independently. Do NOT assume answers follow a pattern.

Return a JSON ARRAY of results, one per question in the SAME ORDER as listed below. Each result object must have:
- correct_key: which option you determined is correct (A/B/C/D)
- trap_type: short label (e.g. "Factual Error", "Misleading Chronology", "Extreme Language", "False Association", "Scope Creep", "Partial Truth", "Qualifier Trap")
- trap_mechanism: 1-2 sentence explanation of how the trap works
- distraction_analysis: object with keys A-D, each value is why that option is wrong (or empty string for the correct answer)
- most_likely_wrong: which wrong option is most tempting (A/B/C/D)
- most_likely_wrong_reason: why that option lures students
- related_concepts: list of concept keywords
- difficulty_tier: integer 1 (easiest) to 10 (hardest)

Return ONLY valid JSON array, no markdown fences.

"""

DEEPSEEK_PROMPT_HEADER = """\
You are a UPSC exam strategist. Analyse the following Prelims questions. For EACH question, identify the correct answer AND the trap structure.

Return a JSON ARRAY of results, one per question in the SAME ORDER as listed below. Each result object must have:
- correct_key: which option is correct (A/B/C/D)
- trap_type: short label (e.g. "Misleading Chronology", "Extreme Language", "Distractor Synonym", "Numerical Illusion", "False Association", "Qualifier Trap", "Scope Creep", "Common Knowledge Mismatch")
- trap_mechanism: 1-2 sentence explanation of how the trap works
- distraction_analysis: object with keys A-D, each value is why that option is wrong (or empty string for the correct answer)
- most_likely_wrong: which wrong option is most tempting (A/B/C/D)
- most_likely_wrong_reason: why that option lures students
- related_concepts: list of concept keywords
- difficulty_tier: integer 1 (easiest) to 10 (hardest)

Use your knowledge of UPSC PYQs to determine the correct answer.

Return ONLY valid JSON array, no markdown fences.

"""

DEEPSEEK_PROMPT_HEADER_INJECTED = """\
You are a UPSC exam strategist. Analyse the following Prelims questions and identify the trap structure for EACH question. The correct answer is provided.

Return a JSON ARRAY of results, one per question in the SAME ORDER as listed below. Each result object must have:
- trap_type: short label (e.g. "Misleading Chronology", "Extreme Language", "Distractor Synonym", "Numerical Illusion", "False Association", "Qualifier Trap", "Scope Creep", "Common Knowledge Mismatch")
- trap_mechanism: 1-2 sentence explanation of how the trap works
- distraction_analysis: object with keys A-D, each value is why that option is wrong (or empty string for the correct answer)
- most_likely_wrong: which wrong option is most tempting (A/B/C/D)
- most_likely_wrong_reason: why that option lures students
- related_concepts: list of concept keywords
- difficulty_tier: integer 1 (easiest) to 10 (hardest)

IMPORTANT: The correct_key is already provided. Do NOT override it. Just analyze the trap structure.

Return ONLY valid JSON array, no markdown fences.

"""

QUESTION_TEMPLATE = """\
=== QUESTION {idx} ===
{text}

Options:
A: {opt_a}
B: {opt_b}
C: {opt_c}
D: {opt_d}
"""

FALLBACK_RESULT = {
    "correct_key": "",
    "trap_type": "unknown",
    "trap_mechanism": "Analysis failed",
    "distraction_analysis": {},
    "most_likely_wrong": "",
    "most_likely_wrong_reason": "",
    "related_concepts": [],
    "difficulty_tier": 5,
}


def _clean_json(text: str) -> str:
    # Extract JSON array or object from surrounding text (thinking output)
    arr_start = text.find("[")
    obj_start = text.find("{")
    if arr_start >= 0 and (obj_start < 0 or arr_start < obj_start):
        start = arr_start
        end = text.rfind("]") + 1
    elif obj_start >= 0:
        start = obj_start
        end = text.rfind("}") + 1
    else:
        start = 0
        end = len(text)
    text = text[start:end]
    text = re.sub(r",\s*}", "}", text)
    text = re.sub(r",\s*]", "]", text)
    return text.strip()


def _build_batch_prompt(questions_slice: list[dict], start_idx: int, answer_key: dict[int, str] | None = None, provider: str = "gemini", existing_trap_types: set | None = None) -> str:
    if provider == "deepseek" and answer_key is None:
        header = DEEPSEEK_PROMPT_HEADER
    elif provider == "deepseek" and answer_key is not None:
        header = DEEPSEEK_PROMPT_HEADER_INJECTED
    elif provider == "gemini" and answer_key is not None:
        header = GEMINI_PROMPT_HEADER
    else:
        header = GEMINI_PROMPT_HEADER_SOLVE

    parts = [header]
    if existing_trap_types:
        parts.append(f"\nExisting trap types for reference (reuse if matching): {', '.join(sorted(existing_trap_types))}\n")

    for i, q in enumerate(questions_slice):
        qnum = q.get("question_number", start_idx + i + 1)
        parts.append(QUESTION_TEMPLATE.format(
            idx=start_idx + i + 1,
            text=q["question_text"],
            opt_a=q["options"].get("A", ""),
            opt_b=q["options"].get("B", ""),
            opt_c=q["options"].get("C", ""),
            opt_d=q["options"].get("D", ""),
        ))
        correct_key = (answer_key or {}).get(qnum)
        if correct_key:
            parts.append(f"Correct Answer: {correct_key}\n")

    return "".join(parts)


def _call_gemini_batch(prompt: str, retries=3) -> list[dict]:
    for attempt in range(retries):
        try:
            resp = protected_gemini_call("ca_analysis", lambda c, m: c.models.generate_content(
                model=m,
                contents=prompt,
                config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(),
                    max_output_tokens=65536,
                ),
            ))
            um = resp.usage_metadata
            print(f"  [tokens] prompt={um.prompt_token_count}, output={um.candidates_token_count}, total={um.total_token_count}")
            cleaned = _clean_json(resp.text)
            data = json.loads(cleaned)
            if isinstance(data, list):
                return data
            return [data]
        except (json.JSONDecodeError, ConnectionError, TimeoutError, Exception):
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise


def _call_deepseek_batch(prompt: str, retries=3) -> list[dict]:
    return call_deepseek_batch(prompt, retries)


def analyze_pdf_questions(
    source_pdf: str,
    questions: list[dict],
    db_session,
    log,
    total: int,
    answer_key: dict[int, str] | None = None,
    provider: str = "gemini",
):
    from models import QuestionAnalysis

    existing_trap_types = set()
    trap_path = DATA_DIR / "trap_summary.json"
    if trap_path.exists():
        try:
            existing_data = json.loads(trap_path.read_text(encoding="utf-8"))
            existing_trap_types = {e["trap_type"] for e in existing_data}
            print(f"  Loaded {len(existing_trap_types)} existing trap types for label normalization")
        except Exception:
            pass

    done = 0

    for chunk_start in range(0, len(questions), BATCH_SIZE):
        chunk = questions[chunk_start:chunk_start + BATCH_SIZE]
        prompt = _build_batch_prompt(chunk, chunk_start, answer_key, provider, existing_trap_types)
        batch_results = []

        try:
            if provider == "deepseek":
                batch_results = _call_deepseek_batch(prompt)
            else:
                batch_results = _call_gemini_batch(prompt)
        except Exception as exc:
            import traceback
            traceback.print_exc()

        if len(batch_results) != len(chunk):
            print(f"  WARNING: {provider} returned {len(batch_results)} results for {len(chunk)} questions (padding with fallback)")
            while len(batch_results) < len(chunk):
                batch_results.append(FALLBACK_RESULT)

        for j, q in enumerate(chunk):
            result = batch_results[j]
            qnum = q.get("question_number")
            ak = answer_key or {}
            official_key = ak.get(qnum) if qnum else None
            correct_key = official_key or result.get("correct_key") or ""
            row = QuestionAnalysis(
                source_pdf=source_pdf,
                question_number=qnum,
                question_text=q["question_text"],
                options=q["options"],
                correct_key=correct_key,
                verified_answer=official_key,
                gemini_correct=(official_key is not None),
                trap_type=result.get("trap_type"),
                trap_mechanism=result.get("trap_mechanism"),
                distraction_analysis=result.get("distraction_analysis"),
                most_likely_wrong=result.get("most_likely_wrong"),
                most_likely_wrong_reason=result.get("most_likely_wrong_reason"),
                related_concepts=result.get("related_concepts", []),
                difficulty_tier=result.get("difficulty_tier", 5),
            )
            db_session.add(row)
            done += 1

        db_session.commit()
        log.progress = f"{done}/{total}"
        db_session.commit()

        time.sleep(2)
