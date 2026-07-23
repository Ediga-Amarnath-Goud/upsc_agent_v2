import re
from api_guardrail import protected_gemini_call
from google.genai import types

GATE_PROMPT = """You are a UPSC current affairs quality gate. Your task is to filter and score news articles against the CA_Summary knowledge base.

CA_Summary (UPSC knowledge base):
{ca_summary}

Below are {count} articles. For each article:
1. Check if it's relevant to UPSC based on the CA_Summary
2. If relevant: output ONE line in this exact format:
id=<id> | score=<0-100> | gs=<GS-I/GS-II/GS-III/GS-IV> | topic=<topic_name>
3. If not relevant: skip it — do NOT output anything for it

Articles (JSON array, each has id, title, summary):
{articles}

Output ONLY the lines for passed articles, one per line. No explanations, no JSON, no markdown.
"""


def llm_quality_gate(all_entries: list[dict], ca_summary: dict) -> list[dict]:
    if not all_entries:
        return []

    payload = [
        {"id": i, "title": e["title"], "summary": (e.get("summary") or "")[:250]}
        for i, e in enumerate(all_entries)
    ]
    prompt = GATE_PROMPT.format(
        ca_summary="",  # avoid bloat — summary is already in payload context
        count=len(payload),
        articles=str(payload),
    )
    try:
        print(f"  LLM gate: Sending {len(all_entries)} articles", flush=True)
        resp = protected_gemini_call("ca_gate", lambda c, m: c.models.generate_content(
            model=m,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=16384,
            ),
        ))
        text = (resp.text or "").strip()
        results = []
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            m = re.match(r'id=(\d+)\s*\|\s*score=(\d+)\s*\|\s*gs=(\S+)\s*\|\s*topic=(.+)', line)
            if not m:
                continue
            results.append({
                "id": int(m.group(1)),
                "relevance_score": int(m.group(2)),
                "gs_linkage": m.group(3),
                "matched_topic": m.group(4).strip(),
            })
    except Exception as exc:
        print(f"  LLM gate failed: {exc}", flush=True)
        return []

    passed = []
    for r in results:
        idx = r.get("id")
        if idx is None or not (0 <= idx < len(all_entries)):
            continue
        entry = all_entries[idx]
        entry["_llm_score"] = r.get("relevance_score", 50)
        entry["_llm_gs_linkage"] = r.get("gs_linkage", "GS-III")
        entry["_llm_matched_topic"] = r.get("matched_topic", "General")
        passed.append(entry)

    passed.sort(key=lambda e: e.get("_llm_score", 0), reverse=True)
    print(f"  LLM gate: {len(passed)} articles passed", flush=True)
    return passed[:100]