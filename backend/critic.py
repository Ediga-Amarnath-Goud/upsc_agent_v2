import json
import os
import time
import requests
from google.genai import types

from api_guardrail import protected_gemini_call
import logger
log = logger.get_logger("critic")

SYSTEM_PROMPT = """Score UPSC Qs 0-1 (pass>=0.7). Check clarity,facts,trap,diff.

{idx}[D{diff}]txt [A:o|B:o|C:o|D:o]->answ t:type

Return JSON: {{"per_question":[{{"index":int,"score":float,"flags":["str"],"suggestion":"str"}}]}}
---
{questions}"""


def review_question_set(questions: list[dict], answer_key: list[dict]) -> dict:
    q_lines = []
    for i, q in enumerate(questions):
        opts = q.get("options", {})
        ak = answer_key[i] if i < len(answer_key) else {}
        q_text = (q.get("question_text", "") or "").replace("\n", " ").replace("|", "/")[:25]
        opt_line = "|".join(f"{k}:{(v or '').replace('|','/').replace('\n',' ')[:10]}" for k, v in sorted(opts.items()))
        correct = ak.get("correct_answer", "?")
        trap = (ak.get("trap_type", "") or "").replace("|", "/")[:10]
        diff = ak.get("difficulty_tier", 5)
        q_lines.append(f"{i}[D{diff}] {q_text} [{opt_line}]->{correct} t:{trap}")

    prompt = SYSTEM_PROMPT.format(questions="\n".join(q_lines))

    # Sarvam primary
    try:
        sarvam_key = os.environ.get("SARVAM_API_KEY")
        if sarvam_key:
            sarvam_url = os.environ.get("SARVAM_BASE_URL", "https://api.sarvam.ai")
            model_name = os.environ.get("SARVAM_MODEL", "sarvam-105b")
            t0 = time.time()
            log.info("Sending %d questions to Sarvam (%s)...", len(questions), model_name)
            resp = requests.post(
                f"{sarvam_url}/v1/chat/completions",
                headers={"api-subscription-key": sarvam_key, "Content-Type": "application/json"},
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 4096,
                },
                timeout=60,
            )
            elapsed = time.time() - t0
            log.info("Sarvam responded in %.1fs with status %d", elapsed, resp.status_code)
            if resp.status_code == 200:
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                result = json.loads(text)
                return _normalize_verdict(result, len(questions))
            else:
                log.warning("Sarvam returned %d: %s", resp.status_code, resp.text[:200])
    except Exception as e:
        log.warning("Sarvam failed: %s", e)

    # Gemini fallback
    try:
        resp = protected_gemini_call("critic", lambda c, m: c.models.generate_content(
            model=m,
            contents=prompt,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(),
                max_output_tokens=8192,
            ),
        ))
        text = (resp.text or "").strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            text = text.rsplit("```", 1)[0].strip()
        import re
        result = json.loads(re.sub(r'[\x00-\x1f]', '', text))
        return _normalize_verdict(result, len(questions))
    except Exception:
        return _fallback_verdict(len(questions))


def _normalize_verdict(result: dict, total: int) -> dict:
    per_q = result.get("per_question", [])
    if len(per_q) != total:
        padded = list(per_q)
        while len(padded) < total:
            padded.append({"index": len(padded), "score": 0.7, "flags": [], "suggestion": ""})
        per_q = padded[:total]

    verdict = "pass"
    for q in per_q:
        score = q.get("score", 0.7)
        if score < 0.5:
            verdict = "fail"
            break
        elif score < 0.7 and verdict != "fail":
            verdict = "review"

    return {
        "overall_verdict": verdict,
        "per_question": per_q,
    }


def _fallback_verdict(total: int) -> dict:
    return {
        "overall_verdict": "review",
        "per_question": [
            {"index": i, "score": 0.7, "flags": ["critic_unavailable"], "suggestion": ""}
            for i in range(total)
        ],
    }
