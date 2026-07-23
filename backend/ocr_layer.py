import json
import io
from PIL import Image

from api_guardrail import protected_gemini_call
from google.genai import types


def read_omr_sheet(image_bytes: bytes, total_questions: int) -> dict[int, str | None]:
    """Read OMR sheet bubbles. Returns {index: 'A'|'B'|'C'|'D'|None}.
    None means unclear/skipped — treated as unanswered."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")

        prompt = (
            f"This is a UPSC Prelims OMR sheet with {total_questions} questions. "
            f"For each question number 1 to {total_questions}, identify which bubble "
            f"(A, B, C, or D) is clearly filled. If no bubble is filled or it\'s unclear, "
            f"use null.\n"
            f"Return a JSON object with:\n"
            f"- responses: array of objects, each with question_index (int, 0-based) "
            f"and response (string A-D or null)\n"
            f"Return ONLY valid JSON, no markdown fences."
        )
        resp = protected_gemini_call("ocr", lambda c, m: c.models.generate_content(
            model=m,
            contents=[prompt, img],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        ))
        data = json.loads(resp.text)
        result = {}
        for r in data.get("responses", []):
            idx = r.get("question_index")
            ans = r.get("response")
            if idx is not None and 0 <= idx < total_questions:
                result[idx] = ans if ans in ("A", "B", "C", "D") else None
        return result
    except Exception:
        return {}


def extract_mains_answer(image_bytes: bytes) -> dict:
    """Extract text from a Mains answer sheet image.
    Returns {"text": str, "confidence": float}."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")

        prompt = (
            "Extract handwritten and typed text from this UPSC Mains answer sheet. "
            "Return JSON with:\n"
            "- text: the extracted answer content (string)\n"
            "- confidence: 0.0 to 1.0 estimating extraction quality\n"
            "Return ONLY valid JSON, no markdown fences."
        )
        resp = protected_gemini_call("ocr", lambda c, m: c.models.generate_content(
            model=m,
            contents=[prompt, img],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        ))
        return json.loads(resp.text)
    except Exception:
        return {"text": "", "confidence": 0.0}
