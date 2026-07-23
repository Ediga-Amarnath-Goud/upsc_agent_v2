import json
from datetime import datetime
from sqlalchemy.orm import Session
from google.genai import types

from models import StudentProfile, QuestionAnalysis, QuestionTopics, ProfileAnalysis
from database import SessionLocal
from api_guardrail import protected_gemini_call

SUBJECT_KEYWORDS = {
    "Polity": ["fundamental rights", "directive principles", "constitution", "parliament", "supreme court",
               "governor", "president", "amendment", "judiciary", "election", "panchayat", "municipality",
               "article", "schedule", "federal", "union", "state", "minister", "bill", "act", "ordinance",
               "writ", "vote", "democracy", "secular", "federalism"],
    "History": ["ancient", "medieval", "modern", "gupta", "maurya", "mughal", "sultanate", "british",
                "independence", "national movement", "gandhi", "nehru", "revolt", "vedic", "indus",
                "harappa", "ashoka", "chola", "akbar", "maratha", "battle", "treaty", "viceroy",
                "partition", "constitutional development", "charter act"],
    "Economy": ["gdp", "gnp", "inflation", "fiscal", "monetary", "rbi", "budget", "five year", "niti",
                "tax", "gst", "subsidy", "poverty", "unemployment", "liberalization", "privatization",
                "globalization", "bank", "insurance", "sebi", "market", "trade", "export", "import",
                "agriculture", "food security", "msp", "public expenditure", "fdi"],
    "Geography": ["monsoon", "climate", "river", "mountain", "soil", "vegetation", "latitude", "longitude",
                  "tropic", "equator", "hemisphere", "plateau", "plain", "desert", "glacier", "cyclone",
                  "earthquake", "volcano", "biosphere", "national park", "wildlife", "sanctuary",
                  "population", "migration", "urban", "rural", "rainfall"],
    "Environment": ["ecology", "ecosystem", "biodiversity", "endangered", "species", "forest", "coral",
                    "wetland", "climate change", "global warming", "pollution", "renewable", "carbon",
                    "greenhouse", "ozone", "conservation", "sustainable", "waste", "recycling"],
    "Science": ["dna", "rna", "protein", "cell", "virus", "bacteria", "vaccine", "satellite", "isro",
                "quantum", "laser", "nuclear", "electron", "proton", "neutron", "gravity", "genome",
                "biotech", "nanotech", "crispr"],
    "Culture": ["dance", "music", "festival", "temple", "sculpture", "painting", "literature", "poetry",
                "sanskrit", "veda", "upanishad", "purana", "epic", "ramayana", "mahabharata",
                "classical", "folk", "tribal", "handicraft", "architecture", "stupa"],
}


def _classify_question(text: str) -> str:
    t = text.lower()
    scores = {}
    for subject, keywords in SUBJECT_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in t)
        if count > 0:
            scores[subject] = count
    if scores:
        return max(scores, key=scores.get)
    return "GS"


def _classify_unclassified(db: Session):
    """Classify unclassified questions by keyword matching. Zero API cost."""
    unclassified = db.query(QuestionAnalysis).filter(~QuestionAnalysis.id.in_(
        db.query(QuestionTopics.question_analysis_id)
    )).all()

    for q in unclassified:
        topic = _classify_question(q.question_text)
        subtopic = topic
        qt = QuestionTopics(
            question_analysis_id=q.id,
            topic=topic,
            subtopic=subtopic,
            confidence=0.7,
        )
        db.add(qt)
    if unclassified:
        db.commit()
        print(f"  Coach: Classified {len(unclassified)} questions by keywords")


def run_analysis(student_id: str = "default"):
    """Run the full profile analysis pipeline. Returns profile_analysis dict."""
    db = SessionLocal()
    try:
        student = db.query(StudentProfile).filter_by(student_id=student_id).first()
        if not student:
            return {"status": "skipped", "reason": "student_not_found"}

        total = student.total_attempted or 0
        if total < 50:
            return {"status": "skipped", "reason": "insufficient_data",
                    "message": f"Only {total} attempts. Need at least 50 for meaningful analysis."}

        _classify_unclassified(db)

        correct = student.total_correct or 0
        per_subject_acc = student.per_subject_accuracy or {}
        trap_stats = student.trap_stats or {}
        subject_elos = student.subject_elos or {}

        weaknesses = []
        strengths = []
        for subj, elo in subject_elos.items():
            acc = per_subject_acc.get(subj, 0)
            entry = {"subject": subj, "accuracy": acc, "elo": elo}
            if acc < 0.5 and elo < 1200:
                weaknesses.append(entry)
            elif acc >= 0.8:
                strengths.append(entry)

        weakest_traps = sorted(
            [(t, s) for t, s in trap_stats.items()],
            key=lambda x: x[1].get("correct", 0) / max(x[1].get("encountered", 1), 1)
        )[:5]

        structured = {
            "overall": {
                "total_attempted": total,
                "total_correct": correct,
                "accuracy": round(correct / total, 4) if total else 0,
                "elo": student.current_elo,
                "most_vulnerable_trap": weakest_traps[0][0] if weakest_traps else None,
            },
            "per_subject": per_subject_acc,
            "weaknesses": weaknesses,
            "strengths": strengths,
            "trap_susceptibility": {
                t: {
                    "encountered": s.get("encountered", 0),
                    "correct": s.get("correct", 0),
                    "accuracy": round(s.get("correct", 0) / max(s.get("encountered", 1), 1), 4),
                }
                for t, s in weakest_traps
            },
        }

        coach_report = _generate_coach_report(structured)

        pa = ProfileAnalysis(
            student_id=student_id,
            structured_data=json.dumps(structured),
            coach_report=coach_report,
            trigger_type="manual",
            question_count_at_analysis=total,
        )
        db.add(pa)
        db.commit()

        print(f"  Coach: Analysis complete for {total} attempts")
        return {"status": "completed", "structured_data": structured, "coach_report": coach_report}
    finally:
        db.close()


def _generate_coach_report(data: dict) -> str:
    """Generate a tutor-voice coach report using 2.5 Flash."""
    prompt = f"""\
You are a UPSC mentor. Based on the following data about a student, write a coaching report in a supportive tutor's voice.

Student Data:
- Overall accuracy: {data['overall']['accuracy']*100:.1f}% ({data['overall']['total_correct']}/{data['overall']['total_attempted']} attempted)
- Current ELO: {data['overall']['elo']}
- Per-subject accuracy: {json.dumps(data['per_subject'])}
- Weakest topics: {json.dumps(data['weaknesses'])}
- Trap susceptibility: {json.dumps(data['trap_susceptibility'])}
- Strength areas: {json.dumps(data['strengths'])}

Write 300-500 words covering:
1. Overall assessment of preparation level
2. Subject-wise breakdown — identify specific weak areas with accuracy figures
3. Trap patterns they fall for most often — be specific about trap types
4. Actionable study plan for the next week with specific topics, resources (NCERT, standard books), and practice targets
5. What to keep doing (strengths to maintain)

Be direct and specific. Mention actual topics and trap types. Output as plain text paragraphs.
"""
    try:
        resp = protected_gemini_call("coach", lambda c, m: c.models.generate_content(
            model=m,
            contents=prompt,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(),
                max_output_tokens=8192,
            ),
        ))
        return resp.text.strip()
    except Exception:
        return "Coach report could not be generated due to API limitations."
