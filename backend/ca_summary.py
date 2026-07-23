import json
import os
from pathlib import Path
from datetime import date
from api_guardrail import protected_gemini_call
from google.genai import types

DATA_DIR = Path(__file__).resolve().parent / "data"
CA_SUMMARY_PATH = DATA_DIR / "ca_summary.json"
SUMMARY_SENTINEL = DATA_DIR / "ca_summary_build_date.txt"

DEFAULT_SUMMARY = {
    "version": 1,
    "last_updated": str(date.today()),
    "high_yield_topics": [],
    "pyq_insights": {"total_questions_analyzed": 0, "subject_breakdown": {}, "trending_keywords": []},
    "academy_insights": {"patterns": [], "filter_prompt": ""},
    "active_focus_areas": [],
}

ACADEMY_SUMMARY_PROMPT = """You are a UPSC content analyst. Your task is to analyze a new Academy Current Affairs PDF to update the existing CA_Summary, which is used to filter daily news.

Current CA_Summary:
{current_summary}

New Academy PDF Markdown:
{academy_markdown}

Focus only on updating the academy insights and active focus areas. Return JSON with the EXACT same structure as the existing summary, but with these updates:
- academy_insights: {{"patterns": [str], "filter_prompt": str}} — Extract new patterns. Write a ~500 token filter_prompt that summarizes the current requirements for news classification.
- active_focus_areas: [str] — 5-10 current high-priority UPSC CA focus areas based on this new academy content.
- high_yield_topics: (keep existing)
- pyq_insights: (keep existing)
"""

PYQ_SUMMARY_PROMPT = """You are a UPSC content analyst. Your task is to analyze new PYQ data to update the existing CA_Summary.

Current CA_Summary:
{current_summary}

New PYQ Classification Data:
{pyq_data}

Focus only on updating the PYQ insights and high-yield topics. Return JSON with the EXACT same structure as the existing summary, but with these updates:
- high_yield_topics: array of {{"topic": str, "weight": 0-1 float, "gs_paper": str, "frequency": int}} — merge new data with existing, update weights.
- pyq_insights: {{"total_questions_analyzed": int, "subject_breakdown": dict, "trending_keywords": [str]}}
- academy_insights: (keep existing)
- active_focus_areas: (keep existing)
"""


def _load_pyq_data(db_session) -> dict:
    from models import DiagnosticQuestions
    questions = db_session.query(DiagnosticQuestions).filter_by(source="pyq", is_active=True).all()
    if not questions:
        return {"total": 0, "by_subject": {}, "keywords": [], "by_ca_sub_topic": {}}

    from diagnostic import _classify_subject
    by_subject = {}
    all_text = []
    for q in questions:
        subj = _classify_subject(q.question_text)
        by_subject.setdefault(subj, 0)
        by_subject[subj] += 1
        all_text.append(q.question_text)

    words = " ".join(all_text).lower().split()
    from collections import Counter
    stopwords = {"the", "a", "an", "is", "are", "was", "were", "of", "in", "to", "and", "for", "on", "with", "as", "by", "at", "from", "its", "it", "that", "this", "which", "what", "who", "not", "be", "has", "have", "do", "does", "did", "but", "or", "if", "so", "no", "all", "each", "every", "both", "most", "some", "any", "none", "one", "two", "more", "less", "other", "than", "also", "very", "just", "about", "above", "below", "between", "through", "during", "before", "after"}
    keywords = [w for w in words if len(w) > 4 and w not in stopwords]
    trend = Counter(keywords).most_common(30)

    # Pipeline A: aggregate by ca_sub_topic when classified data is available
    by_ca_sub_topic = {}
    classified = [q for q in questions if q.ca_sub_topic]
    if classified:
        for q in classified:
            by_ca_sub_topic.setdefault(q.ca_sub_topic, 0)
            by_ca_sub_topic[q.ca_sub_topic] += 1

    return {
        "total": len(questions),
        "by_subject": by_subject,
        "keywords": [{"keyword": k, "count": c} for k, c in trend],
        "by_ca_sub_topic": by_ca_sub_topic,
    }


def classify_pyq_ca_topics(db_session) -> int:
    """Pipeline A: Classify PYQ CA questions in one single LLM call.
    Returns count of newly classified rows. Idempotent — skips already-classified rows."""
    from models import DiagnosticQuestions
    unclassified = (
        db_session.query(DiagnosticQuestions)
        .filter(
            DiagnosticQuestions.source == "pyq",
            DiagnosticQuestions.is_active == True,
            DiagnosticQuestions.ca_sub_topic == None,
        )
        .all()
    )
    if not unclassified:
        print("  CA Pipeline A: all PYQs already classified")
        return 0

    CLASSIFY_PROMPT = """You are a UPSC PYQ classifier. For each question, identify:
- ca_sub_topic: the most specific CA sub-topic tested (e.g. "India-China border", "COP28 outcomes", "Chandrayaan-3", "GST Council decisions", "Fundamental Rights Article 21")
- question_type: one of [direct, twisted_multi, assertion_reason, static_linked]

Return ONLY valid JSON in this exact format:
{{"<id>": {{"ca_sub_topic": "...", "question_type": "..."}}}}

Questions:
{questions}"""

    questions_text = "\n".join(
        f"{q.id}: {q.question_text[:300]}"
        for q in unclassified
    )
    prompt = CLASSIFY_PROMPT.format(questions=questions_text)

    try:
        resp = protected_gemini_call("ca_analysis", lambda c, m: c.models.generate_content(
            model=m,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                max_output_tokens=8192,
            ),
        ))
        results = json.loads(resp.text)
        classified_count = 0
        for q in unclassified:
            row = results.get(str(q.id))
            if row:
                q.ca_sub_topic = row.get("ca_sub_topic")
                q.question_type = row.get("question_type")
                classified_count += 1
        db_session.commit()
        print(f"  CA Pipeline A: classified {classified_count}/{len(unclassified)} PYQs")
        return classified_count
    except Exception as exc:
        print(f"  CA Pipeline A: classification failed: {exc}")
        db_session.rollback()
        return 0


def _load_current_summary() -> dict:
    if CA_SUMMARY_PATH.exists():
        try:
            return json.loads(CA_SUMMARY_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return DEFAULT_SUMMARY.copy()


def _write_summary_safe(summary: dict):
    tmp = CA_SUMMARY_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    tmp.replace(CA_SUMMARY_PATH)


def update_summary_with_academy(academy_markdown: str) -> dict:
    current = _load_current_summary()

    prompt = ACADEMY_SUMMARY_PROMPT.format(
        current_summary=json.dumps(current, indent=2)[:3000],
        academy_markdown=academy_markdown[:30000],
    )

    try:
        resp = protected_gemini_call("ca_analysis", lambda c, m: c.models.generate_content(
            model=m,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                max_output_tokens=32768,
            ),
        ))
        summary = json.loads(resp.text)
        summary["version"] = current.get("version", 1) + 1
        summary["last_updated"] = str(date.today())
        summary["high_yield_topics"] = summary.get("high_yield_topics", current.get("high_yield_topics", []))
        summary["pyq_insights"] = summary.get("pyq_insights", current.get("pyq_insights", {}))
    except Exception as exc:
        print(f"  Academy summary update failed: {exc}")
        return current

    _write_summary_safe(summary)
    return summary


def update_summary_with_pyqs(db_session) -> dict:
    current = _load_current_summary()

    # Skip if already built today with PYQ data present
    if current.get("pyq_insights", {}).get("total_questions_analyzed", 0) > 0 and SUMMARY_SENTINEL.exists():
        last_build = SUMMARY_SENTINEL.read_text().strip()
        if last_build == str(date.today()):
            print("  CA_Summary PYQ update: already built today, skipping", flush=True)
            return current

    pyq_data = _load_pyq_data(db_session)
    if pyq_data["total"] == 0:
        print("  CA_Summary PYQ update: no PYQ data, skipping LLM call", flush=True)
        current["last_updated"] = str(date.today())
        return current

    prompt = PYQ_SUMMARY_PROMPT.format(
        current_summary=json.dumps(current, indent=2)[:3000],
        pyq_data=json.dumps(pyq_data, indent=2)[:10000],
    )

    try:
        resp = protected_gemini_call("ca_analysis", lambda c, m: c.models.generate_content(
            model=m,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                max_output_tokens=32768,
            ),
        ))
        summary = json.loads(resp.text)
        # Handle LLM returning a JSON array instead of object
        if isinstance(summary, list):
            summary = {"version": current.get("version", 1) + 1, "pyq_analysis": summary, "high_yield_topics": [], "pyq_insights": {"total_questions_analyzed": pyq_data["total"], "subject_breakdown": pyq_data["by_subject"], "trending_keywords": pyq_data["keywords"]}, "academy_insights": current.get("academy_insights", {}), "active_focus_areas": current.get("active_focus_areas", [])}
        summary["version"] = current.get("version", 1) + 1
        summary["last_updated"] = str(date.today())
        summary["academy_insights"] = summary.get("academy_insights", current.get("academy_insights", {}))
        summary["active_focus_areas"] = summary.get("active_focus_areas", current.get("active_focus_areas", []))
    except Exception as exc:
        print(f"  PYQ summary update failed (will retry next startup): {exc}", flush=True)
        return current

    _write_summary_safe(summary)
    SUMMARY_SENTINEL.write_text(str(date.today()))
    return summary


def load_ca_summary() -> dict:
    return _load_current_summary()
