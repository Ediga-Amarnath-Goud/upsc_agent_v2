import os
import json
import re
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DATA_DIR = Path(__file__).resolve().parent / "data"
TRACKER_PATH = DATA_DIR / "deepseek_usage_tracker.json"


class DeepSeekGuardrail:
    def __init__(self, daily_max=50, rpm_max=20):
        self.daily_max = daily_max
        self.rpm_max = rpm_max
        self.sliding_window = []
        DATA_DIR.mkdir(exist_ok=True)
        self._ensure_tracker()

    def _ensure_tracker(self):
        if not TRACKER_PATH.exists():
            with open(TRACKER_PATH, "w") as f:
                json.dump({"date": str(datetime.utcnow().date()), "count": 0}, f)

    def _get_daily_count(self) -> int:
        self._ensure_tracker()
        try:
            with open(TRACKER_PATH, "r") as f:
                data = json.load(f)
            today = str(datetime.utcnow().date())
            if data.get("date") != today:
                data = {"date": today, "count": 0}
                with open(TRACKER_PATH, "w") as f:
                    json.dump(data, f)
            return data["count"]
        except Exception:
            return 0

    def _increment_daily_count(self):
        try:
            with open(TRACKER_PATH, "r") as f:
                data = json.load(f)
            data["count"] += 1
            with open(TRACKER_PATH, "w") as f:
                json.dump(data, f)
        except Exception:
            pass

    def verify_and_pace(self):
        daily = self._get_daily_count()
        if daily >= self.daily_max:
            raise RuntimeError("DeepSeek daily API limit exhausted. Try again tomorrow.")

        now = time.time()
        self.sliding_window = [t for t in self.sliding_window if now - t < 60]

        if len(self.sliding_window) >= self.rpm_max:
            oldest = self.sliding_window[0]
            wait = 60.0 - (now - oldest) + 0.5
            if wait > 0:
                time.sleep(wait)
                now = time.time()
                self.sliding_window = [t for t in self.sliding_window if now - t < 60]

        self.sliding_window.append(time.time())
        self._increment_daily_count()


guardrail = DeepSeekGuardrail()


def _clean_json(text: str) -> str:
    text = re.sub(r",\s*}", "}", text)
    text = re.sub(r",\s*]", "]", text)
    return text.strip()


def execute_protected_deepseek_call():
    guardrail.verify_and_pace()
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    model_name = os.environ.get("DEEPSEEK_MODEL") or "deepseek/deepseek-v4-pro"

    if deepseek_key:
        client = OpenAI(
            base_url="https://api.deepseek.com",
            api_key=deepseek_key,
        )
        return client, model_name
    elif openrouter_key:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=openrouter_key,
        )
        return client, model_name
    raise RuntimeError("Neither DEEPSEEK_API_KEY nor OPENROUTER_API_KEY set in environment")


def call_deepseek_batch(prompt: str, retries=3) -> list[dict]:
    for attempt in range(retries):
        try:
            client, model = execute_protected_deepseek_call()
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=65536,
            )
            content = resp.choices[0].message.content
            if resp.usage:
                print(f"  [tokens] prompt={resp.usage.prompt_tokens}, output={resp.usage.completion_tokens}, total={resp.usage.total_tokens}")
            cleaned = _clean_json(content)
            data = json.loads(cleaned)
            if isinstance(data, list):
                return data
            return [data]
        except Exception:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
