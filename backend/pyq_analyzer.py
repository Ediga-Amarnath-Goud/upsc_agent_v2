import random
import logger
log = logger.get_logger("pyq_analyzer")

SUBJECT_KEYWORDS: dict[str, list[str]] = {
    "History": ["history", "ancient", "medieval", "modern", "indian", "freedom", "nationalism", "gandhi"],
    "Polity": ["polity", "constitution", "parliament", "judiciary", "rights", "governance", "panchayat"],
    "Economy": ["economy", "economics", "gdp", "inflation", "budget", "banking", "finance"],
    "Geography": ["geography", "geo", "climate", "monsoon", "river", "soil", "population"],
    "Environment": ["environment", "ecology", "biodiversity", "climate change", "pollution", "forest"],
    "Science": ["science", "tech", "space", "isro", "biotech", "nanotech", "physics", "chemistry", "biology"],
    "Culture": ["culture", "art", "architecture", "sculpture", "painting", "heritage"],
}


def subject_from_topic(topic: str) -> str | None:
    t = topic.lower()
    for subj, kws in SUBJECT_KEYWORDS.items():
        if any(kw in t for kw in kws):
            return subj
    return None


def get_reference_questions(
    db_session,
    topic: str,
    subject: str,
    max_samples: int = 5,
) -> list[dict]:
    from models import QuestionAnalysis, QuestionTopics

    subj = subject_from_topic(topic) or subject or "GS"
    keyword = f"%{subj}%"

    # Prefer matching by classified topic (QuestionTopics table)
    rows = (
        db_session.query(QuestionAnalysis)
        .join(QuestionTopics, QuestionAnalysis.id == QuestionTopics.question_analysis_id)
        .filter(QuestionTopics.topic.ilike(keyword))
        .limit(max_samples * 3)
        .all()
    )
    if rows:
        log.debug("Matched %d by QuestionTopics.topic", len(rows))
    else:
        # Fallback: match by PDF filename
        rows = (
            db_session.query(QuestionAnalysis)
            .filter(QuestionAnalysis.source_pdf.ilike(keyword))
            .limit(max_samples * 3)
            .all()
        )
        if rows:
            log.debug("Matched %d by source_pdf filename", len(rows))
    if not rows:
        # Fallback: any recent questions
        rows = db_session.query(QuestionAnalysis).order_by(
            QuestionAnalysis.created_at.desc()
        ).limit(max_samples * 3).all()
        log.debug("No topic/filename match — using %d recent questions", len(rows))

    if not rows:
        return []

    sampled = random.sample(rows, min(max_samples, len(rows)))
    return [
        {
            "question_text": r.question_text,
            "options": r.options,
            "correct_key": r.correct_key,
            "trap_type": r.trap_type,
            "difficulty_tier": r.difficulty_tier,
        }
        for r in sampled
    ]
