import json
from sqlalchemy.orm import Session

from models import StudentProfile, CuratedCA
from api_guardrail import protected_gemini_call
from google.genai import types
import logger

log = logger.get_logger("ca_trap")


def _get_student_weakest_trap(db_main: Session) -> str:
    """Dynamically read the student's weakest trap type from profile stats."""
    student = db_main.query(StudentProfile).filter_by(student_id="default").first()
    if not student or not student.trap_stats:
        return "Factual Error"
    t_stats = student.trap_stats or {}
    if not t_stats:
        return "Factual Error"
    worst = min(
        t_stats.items(),
        key=lambda x: x[1].get("correct", 0) / max(x[1].get("encountered", 1), 1),
    )
    return worst[0]


TRAP_PROMPT = """\
You are an adversarial UPSC Question Setter. Analyze this analytical issue context:

Core Issue: {title}
Taxonomy: {gs_linkage}
High-Yield Facts: {high_yield_facts}

The student is highly vulnerable to '{weakest_trap}' traps.
Generate a valid JSON object with these fields:
- trap_type: the trap category (must relate to the weakness above)
- mechanism: 1-2 sentences explaining how a question-setter would manipulate this news fact to trick a student
- elimination_clue: the logical anchor used to dismantle the trap during testing

Return ONLY valid JSON, no markdown fences.
"""


def generate_trap_prediction(
    db_main: Session,
    db_ca: Session,
    article_id: int,
) -> dict | None:
    """Generate personalized trap prediction for a CuratedCA article."""
    article = db_ca.query(CuratedCA).filter_by(id=article_id).first()
    if not article:
        log.warning("CuratedCA article %d not found", article_id)
        return None

    weakest_trap = _get_student_weakest_trap(db_main)

    facts_raw = article.prelims_high_yield_facts
    try:
        facts_list = json.loads(facts_raw) if isinstance(facts_raw, str) else facts_raw
    except (json.JSONDecodeError, TypeError):
        facts_list = []

    prompt = TRAP_PROMPT.format(
        title=article.title,
        gs_linkage=article.gs_linkage,
        high_yield_facts="\n".join(f"- {f}" for f in facts_list[:5]) if facts_list else "N/A",
        weakest_trap=weakest_trap,
    )

    try:
        resp = protected_gemini_call("ca_analysis", lambda c, m: c.models.generate_content(
            model=m,
            contents=prompt,
            config=types.GenerateContentConfig(max_output_tokens=1024),
        ))
        text = (resp.text or "").strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            text = text.rsplit("```", 1)[0].strip()
        import re
        data = json.loads(re.sub(r'[\x00-\x1f]', '', text))
        return data
    except Exception as exc:
        log.error("Trap prediction failed for article %d: %s", article_id, exc)
        return None


def inject_trap_predictions_for_all(
    db_main: Session,
    db_ca: Session,
    limit: int = 10,
) -> int:
    """Generate trap predictions for CuratedCA articles that don't have one yet."""
    articles = (
        db_ca.query(CuratedCA)
        .filter(CuratedCA.predicted_traps.is_(None))
        .order_by(CuratedCA.created_at.desc())
        .limit(limit)
        .all()
    )
    count = 0
    for article in articles:
        prediction = generate_trap_prediction(db_main, db_ca, article.id)
        if prediction:
            article.predicted_traps = json.dumps(prediction)
            db_ca.commit()
            count += 1
            log.info("Injected trap prediction for CuratedCA article %d", article.id)
    return count
