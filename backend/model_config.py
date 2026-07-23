import os

LAYER_MODELS = {
    "diagnostic": os.getenv("DIAGNOSTIC_MODEL", "gemini-3-flash-preview"),
    "ocr": os.getenv("OCR_MODEL", "gemini-3.1-flash-lite"),
    "coach": os.getenv("COACH_MODEL", "gemini-2.5-flash"),
    "engine": os.getenv("ENGINE_MODEL", "gemini-3.5-flash"),
    "critic": os.getenv("CRITIC_MODEL", "gemini-3.1-flash-lite"),
    "ca_parser": os.getenv("CA_MODEL", "gemini-3.1-flash-lite"),
    "ca_analysis": os.getenv("CA_ANALYSIS_MODEL", "gemini-3-flash-preview"),
    "ca_gate": os.getenv("CA_GATE_MODEL", "gemini-3-flash-preview"),
    "ca_restructure": os.getenv("CA_RESTRUCTURE_MODEL", "gemini-3.1-flash-lite"),
}

LAYER_TIER = {
    "diagnostic": "gemini-3-flash-preview",
    "ocr": "abundant",
    "coach": "gemini-2.5-flash",
    "engine": "gemini-3.5-flash",
    "critic": "abundant",
    "ca_parser": "abundant",
    "ca_analysis": "gemini-3-flash-preview",
    "ca_gate": "gemini-3-flash-preview",
    "ca_restructure": "gemini-3.1-flash-lite",
}
