import json
import time
import textwrap
from api_guardrail import protected_gemini_call
from schemas import GeneratedQuestion, AnswerKeyEntry
from pyq_analyzer import get_reference_questions
import math_utils
from google import genai
from google.genai import types
import logger
log = logger.get_logger("generator")

GENERATION_PROMPT = textwrap.dedent("""\
You are a UPSC Prelims paper setter. Generate {count} questions on "{topic}" at varying difficulty.

{RULES}

{REF_SECTION}

{PRIORITY_SECTION}

{CA_SECTION}

Return a JSON object with two arrays:
1. "questions" — each has: question_text (string), options (object with A/B/C/D keys as strings), difficulty_tier (1–10)
2. "answer_key" — each has: correct_answer (A/B/C/D), correct_explanation (string), trap_type (string), trap_explanation (string), most_likely_wrong_answer (A/B/C/D), most_likely_wrong_reason (string), difficulty_tier (int matching the question)

Return ONLY valid JSON, no markdown fences.
""")

RULES_TEXT = textwrap.dedent("""\
Rules:
- Each question must have exactly 4 options (A, B, C, D).
- Difficulty tiers: 1-3 Easy, 4-6 Moderate, 7-8 Hard, 9-10 Expert.
- Mix difficulty across the set.
- Include at least one trap from the priority list per every 2 questions.
- Questions must be factually correct and exam-relevant.
- Avoid ambiguous wording.
- Include at least 2 questions referencing recent/current events from 2025-2026. Use Current Affairs context where relevant.
- Each wrong option must be a plausible statement a prepared student might choose. Avoid obviously wrong options.
""")


def _build_reference_section(db_session, subject: str, topic: str, count: int = 10) -> str:
    refs = get_reference_questions(db_session, topic, subject, max_samples=5)
    if not refs:
        return ""
    lines = [f"\nReference PYQs for difficulty calibration (target ~{subject}):"]
    for r in refs:
        lines.append(
            f"- [{r['trap_type'] or 'general'} | tier {r['difficulty_tier']}] "
            f"{r['question_text'][:120]}"
        )
    # Distribution hint for broad topics
    if count >= 8:
        subjects_seen = set()
        from diagnostic import _classify_subject
        for r in refs:
            subjects_seen.add(_classify_subject(r['question_text']))
        if len(subjects_seen) >= 2:
            per_subj = max(1, count // len(subjects_seen))
            lines.append(
                f"\nDistribute roughly {per_subj} questions per sub-topic: "
                f"{', '.join(sorted(subjects_seen)[:4])}."
            )
    return "\n".join(lines)


def _build_priority_section(student, count: int, topic: str) -> str:
    matrix = math_utils.get_priority_matrix(student, count=count, topic=topic)
    if not matrix:
        return ""
    lines = ["\nPriority slots (fill these trap types in order):"]
    for slot in matrix:
        lines.append(
            f"  Slot {slot['slot']}: subject={slot['subject']}, "
            f"trap={slot['trap']}, difficulty={slot['difficulty_tier']}, "
            f"reason={slot['reason']}"
        )
    return "\n".join(lines)


def generate_test_content(
    topic: str,
    subject: str,
    count: int,
    student,
    db_session,
    quality_check: bool = True,
) -> tuple[list[GeneratedQuestion], list[AnswerKeyEntry]]:
    ref_section = _build_reference_section(db_session, subject, topic, count=count)
    priority_section = _build_priority_section(student, count, topic)

    # Student context for difficulty calibration
    elo = student.current_elo or 1200
    attempted = student.total_attempted or 0
    correct = student.total_correct or 0
    accuracy = (correct / attempted * 100) if attempted > 0 else 50
    student_context = (
        f"\nStudent context: ELO={elo}, overall accuracy={accuracy:.0f}%. "
        f"Calibrate difficulty to challenge without overwhelming."
    )
    priority_section += student_context

    # Inject current affairs context
    ca_section = ""
    try:
        from current_affairs import get_relevant_entries
        ca_entries = get_relevant_entries(topic, limit=3, db=db_session)
        if ca_entries:
            ca_lines = ["\nCurrent Affairs context (use for current-event questions):"]
            for ca in ca_entries:
                ca_lines.append(
                    f"- [{ca['category']}] {ca['title']}\n"
                    f"  Summary: {ca['summary'][:150]}"
                )
            ca_section = "\n".join(ca_lines)
    except Exception:
        pass

    prompt = GENERATION_PROMPT.format(
        count=count,
        topic=topic,
        RULES=RULES_TEXT,
        REF_SECTION=ref_section,
        PRIORITY_SECTION=priority_section,
        CA_SECTION=ca_section or "",
    )

    log.info("Generating %d questions on '%s'...", count, topic)
    t0 = time.time()
    try:
        resp = protected_gemini_call("engine", lambda c, m: c.models.generate_content(
            model=m,
            contents=prompt,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(),
                max_output_tokens=65536,
            ),
        ))
    except Exception as e:
        log.error("Gemini API call failed: %s", e)
        if hasattr(e, 'code'):
            log.error("Error code: %s", e.code)
        if hasattr(e, 'message'):
            log.error("Error message: %s", e.message)
        raise
    elapsed = time.time() - t0
    if resp.usage_metadata:
        um = resp.usage_metadata
        log.info("API done in %.1fs — prompt=%d output=%d total=%d tokens",
                 elapsed, um.prompt_token_count, um.candidates_token_count, um.total_token_count)
    else:
        log.info("API done in %.1fs (no usage metadata)", elapsed)

    if not resp.text or not resp.text.strip():
        log.error("Empty response from model")
        raise ValueError("Empty response from model")

    text = resp.text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0].strip()
    import re
    text = re.sub(r'[\x00-\x1f]', '', text)

    if not text:
        log.error("Empty text after stripping fences/control chars")
        raise ValueError("Empty response after cleanup")

    try:
        raw = json.loads(text)
    except json.JSONDecodeError as e:
        log.error("JSON parse failed: %s. First 500 chars: %s", e, text[:500])
        raise

    if "questions" not in raw or "answer_key" not in raw:
        log.error("Response missing required keys. Available: %s", list(raw.keys()))
        raise ValueError(f"Missing keys: questions or answer_key")

    raw_qs = raw["questions"]
    raw_ak = raw["answer_key"]
    if len(raw_qs) != len(raw_ak):
        log.error("Mismatched arrays: %d questions, %d answer_key entries", len(raw_qs), len(raw_ak))
        # Truncate to shorter length so we don't crash
        min_len = min(len(raw_qs), len(raw_ak))
        raw_qs = raw_qs[:min_len]
        raw_ak = raw_ak[:min_len]

    try:
        questions = [GeneratedQuestion(**q) for q in raw_qs]
        answer_key = [AnswerKeyEntry(**k) for k in raw_ak]
    except Exception as e:
        log.error("Pydantic parse failed: %s", e)
        if raw_qs:
            log.error("First raw question keys: %s", list(raw_qs[0].keys()) if raw_qs else "N/A")
        raise

    log.info("Parsed %d questions, %d answer key entries", len(questions), len(answer_key))

    # Single-pass critic
    if quality_check:
        try:
            from critic import review_question_set
            q_dicts = [q.model_dump() for q in questions]
            ak_dicts = [k.model_dump() for k in answer_key]
            t1 = time.time()
            verdict = review_question_set(q_dicts, ak_dicts)
            log.info("Critic done in %.1fs — verdict=%s", time.time() - t1, verdict.get("overall_verdict"))
            if verdict["overall_verdict"] == "fail":
                flagged = [
                    q for q in verdict["per_question"] if q.get("score", 1) < 0.5
                ]
                log.warning("Critic flagged %d questions (accepting anyway)", len(flagged))
        except Exception as e:
            log.warning("Critic unavailable: %s", e)

    return questions, answer_key
