import os
import json
import time
from datetime import datetime
from pathlib import Path
from google.genai import types
from google.genai.errors import ServerError, ClientError
import logger
log = logger.get_logger("api_guardrail")

DATA_DIR = Path(__file__).resolve().parent / "data"

TIER_DEFS = {
    "gemini-3-flash-preview": {"daily_max": 20, "rpm_max": 5},
    "gemini-2.5-flash": {"daily_max": 20, "rpm_max": 5},
    "gemini-2.5-flash-lite": {"daily_max": 20, "rpm_max": 5},
    "gemini-3.5-flash": {"daily_max": 20, "rpm_max": 5},
    "abundant": {"daily_max": 500, "rpm_max": 15},
}

_instances = {}


def _get_guardrail(key: str) -> "TierGuardrail":
    if key not in _instances:
        defs = TIER_DEFS.get(key, TIER_DEFS["gemini-3-flash-preview"])
        _instances[key] = TierGuardrail(key, **defs)
    return _instances[key]


class TierGuardrail:
    def __init__(self, tier_name: str, daily_max: int, rpm_max: int):
        self.tier_name = tier_name
        self.daily_max = daily_max
        self.rpm_max = rpm_max
        self.sliding_window = []
        self.tracker_path = DATA_DIR / f"api_usage_{tier_name}.json"
        DATA_DIR.mkdir(exist_ok=True)
        self._ensure_tracker()

    def _ensure_tracker(self):
        if not self.tracker_path.exists():
            with open(self.tracker_path, "w") as f:
                json.dump({"date": str(datetime.utcnow().date()), "count": 0}, f)

    def _get_daily_count(self) -> int:
        self._ensure_tracker()
        try:
            with open(self.tracker_path, "r") as f:
                data = json.load(f)
            today = str(datetime.utcnow().date())
            if data.get("date") != today:
                data = {"date": today, "count": 0}
                with open(self.tracker_path, "w") as f:
                    json.dump(data, f)
            return data["count"]
        except Exception:
            return 0

    def _increment_daily_count(self):
        try:
            with open(self.tracker_path, "r") as f:
                data = json.load(f)
            data["count"] += 1
            with open(self.tracker_path, "w") as f:
                json.dump(data, f)
        except Exception:
            pass

    def check(self):
        """Verify limits without incrementing. Sleeps if RPM exceeded. Raises if daily limit hit."""
        daily = self._get_daily_count()
        if daily >= self.daily_max:
            log.error("Daily limit hit for '%s': %d/%d", self.tier_name, daily, self.daily_max)
            raise RuntimeError(
                f"Daily API limit exhausted for '{self.tier_name}' "
                f"({self.daily_max}/day). Try again tomorrow."
            )
        now = time.time()
        self.sliding_window = [t for t in self.sliding_window if now - t < 60]
        if len(self.sliding_window) >= self.rpm_max:
            oldest = self.sliding_window[0]
            wait = 60.0 - (now - oldest) + 0.5
            log.info("Rate limit pacing for '%s': waiting %.1fs", self.tier_name, wait)
            if wait > 0:
                time.sleep(wait)
                self.sliding_window = [t for t in self.sliding_window if now - t < 60]

    def record(self):
        """Increment counters after a successful API response."""
        self.sliding_window.append(time.time())
        self._increment_daily_count()

    def verify_and_pace(self):
        """Legacy: check + record (increments before API call)."""
        self.check()
        self.record()


# Backward compat instances
tier1_scarce = _get_guardrail("gemini-3-flash-preview")
tier2_abundant = _get_guardrail("abundant")
guardrail = tier1_scarce


def execute_protected_gemini_call(tier: str = "scarce"):
    """Legacy — use protected_gemini_call() instead."""
    from google import genai
    gr = tier2_abundant if tier == "abundant" else tier1_scarce
    gr.verify_and_pace()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in environment")
    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=600000),
    )
    model_name = os.environ.get("GEMINI_MODEL") or "gemini-3-flash-preview"
    return client, model_name


def execute_layer_call(layer_key: str):
    """Legacy — use protected_gemini_call() for refund-on-failure behavior."""
    from google import genai
    from model_config import LAYER_MODELS, LAYER_TIER

    model_name = LAYER_MODELS.get(layer_key, "gemini-3-flash-preview")
    tier_key = LAYER_TIER.get(layer_key, "gemini-3-flash-preview")
    gr = _get_guardrail(tier_key)
    gr.verify_and_pace()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in environment")

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=600000),
    )
    return client, model_name


def protected_gemini_call(layer_key: str, call_fn, retries=4):
    """Check limits -> call -> record only on success.
    Retries transient errors (503, 429) with exponential backoff (5s, 10s, 20s, 40s).
    Returns the result of call_fn(client, model_name).
    """
    from google import genai
    from model_config import LAYER_MODELS, LAYER_TIER

    model_name = LAYER_MODELS.get(layer_key, "gemini-3-flash-preview")
    tier_key = LAYER_TIER.get(layer_key, "gemini-3-flash-preview")
    gr = _get_guardrail(tier_key)
    gr.check()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in environment")

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=600000),
    )

    last_exc = None
    for attempt in range(retries + 1):
        try:
            result = call_fn(client, model_name)
            gr.record()
            return result
        except (ServerError, ClientError) as exc:
            last_exc = exc
            if attempt < retries:
                wait = (2 ** attempt) * 5
                print(f"  API transient error, retry {attempt+1}/{retries} in {wait}s: {exc}", flush=True)
                time.sleep(wait)
                continue
            raise
        except Exception:
            gr.record()
            raise

    raise last_exc or RuntimeError("protected_gemini_call: unexpected exit")
