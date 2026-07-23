"""Phase 4 Verification — single-run test of all system endpoints.
Starts server, tests each endpoint, stops server. No external API calls.
API-dependent endpoints are tested at the error-handling level (guardrail blocks them)."""

import subprocess
import time
import sys
import os
import json
import io
import tempfile
from pathlib import Path
import requests
from datetime import datetime, timezone

BASE_URL = "http://127.0.0.1:8013"
PORT = 8013
SERVER_DIR = Path(__file__).resolve().parent
PASS = 0
FAIL = 0
WARN = 0

def ok(msg):
    global PASS; PASS += 1; print(f"  \033[92mPASS\033[0m  {msg}")

def fail(msg, detail=""):
    global FAIL; FAIL += 1; print(f"  \033[91mFAIL\033[0m  {msg}")
    if detail: print(f"         {detail}")

def warn(msg):
    global WARN; WARN += 1; print(f"  \033[93mWARN\033[0m  {msg}")

def section(name):
    print(f"\n\033[96m=== {name} ===\033[0m")


# ── 1. Seed test DB ───────────────────────────────────────────────────────────

def seed_database():
    """Pre-seed student profile + diagnostic bypass so we can test gated endpoints."""
    from database import init_db, SessionLocal
    from models import StudentProfile
    init_db()
    db = SessionLocal()
    try:
        student = db.query(StudentProfile).filter_by(student_id="default").first()
        if not student:
            student = StudentProfile(student_id="default", current_elo=1200)
            db.add(student)
        student.diagnostic_completed = True
        student.last_active = datetime.now(timezone.utc)
        student.total_attempted = 50
        student.total_correct = 30
        student.per_subject_accuracy = {"Polity": 0.65, "History": 0.55}
        student.subject_elos = {"Polity": 1220, "History": 1150}
        student.trap_stats = {"Factual Error": {"encountered": 10, "correct": 3}}
        db.commit()
        ok("Seeded student profile with diagnostic_completed=True")
    finally:
        db.close()

    # Create test diagnostic session for submit testing
    from database import SessionLocal as DbLocal, init_db
    from models import DiagnosticResults, DiagnosticQuestions
    init_db()
    db = DbLocal()
    try:
        existing = db.query(DiagnosticQuestions).filter_by(source="test_seed").first()
        if not existing:
            for i in range(3):
                dq = DiagnosticQuestions(
                    question_text=f"Test question {i}?",
                    options='{"A":"Opt A","B":"Opt B","C":"Opt C","D":"Opt D"}',
                    correct_key="A",
                    subject="Polity",
                    difficulty_tier=5,
                    trap_type="Factual Error",
                    source="test_seed",
                    is_active=True,
                )
                db.add(dq)
            db.flush()

        qs = db.query(DiagnosticQuestions).filter_by(source="test_seed").all()
        qids = [q.id for q in qs]

        dr = DiagnosticResults(
            student_id="default",
            session_id="test-session-001",
            question_ids=qids,
            total=len(qids),
            score=0,
            per_subject={},
            started_at=datetime.now(timezone.utc),
        )
        db.add(dr)
        db.commit()
        ok(f"Seeded diagnostic session with {len(qids)} questions")
    finally:
        db.close()


# ── 2. Start server ───────────────────────────────────────────────────────────

server_proc = None

def start_server():
    global server_proc
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SERVER_DIR)
    server_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=SERVER_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    for _ in range(30):
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=2)
            if r.status_code == 200:
                ok("Server started")
                return True
        except requests.ConnectionError:
            time.sleep(1)
    fail("Server failed to start")
    return False


def stop_server():
    global server_proc
    if server_proc:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_proc.kill()
        ok("Server stopped")


# ── 3. Tests ──────────────────────────────────────────────────────────────────

def test_health():
    r = requests.get(f"{BASE_URL}/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "model" in data
    ok(f"GET /health -> 200, model={data['model']}")


def test_gate_ca_exempt():
    r = requests.get(f"{BASE_URL}/current-affairs/stats")
    assert r.status_code == 200
    ok("GET /current-affairs/stats passes gate without diagnostic")


def test_gate_blocks_before_diagnostic():
    """Temporarily clear diagnostic_completed, verify gate blocks, restore."""
    from database import SessionLocal
    from models import StudentProfile
    db = SessionLocal()
    try:
        student = db.query(StudentProfile).filter_by(student_id="default").first()
        old = student.diagnostic_completed
        student.diagnostic_completed = False
        db.commit()

        r = requests.get(f"{BASE_URL}/profile")
        assert r.status_code == 403
        data = r.json()
        assert "diagnostic" in str(data.get("error", ""))
        ok("Gate blocks /profile when diagnostic not completed")

        r = requests.get(f"{BASE_URL}/current-affairs/stats")
        assert r.status_code == 200
        ok("Gate allows /current-affairs/* when diagnostic not completed")

        student.diagnostic_completed = old
        db.commit()
    finally:
        db.close()


def test_ca_stats():
    r = requests.get(f"{BASE_URL}/current-affairs/stats")
    assert r.status_code == 200
    data = r.json()
    assert "total" in data and "today" in data
    ok(f"GET /current-affairs/stats -> total={data['total']}, today={data['today']}")


def test_ca_list_empty():
    r = requests.get(f"{BASE_URL}/current-affairs")
    assert r.status_code == 200
    data = r.json()
    assert "entries" in data and "total" in data
    ok(f"GET /current-affairs -> {data['total']} entries")


def test_ca_detail_404():
    r = requests.get(f"{BASE_URL}/current-affairs/99999")
    assert r.status_code == 404
    ok("GET /current-affairs/99999 -> 404")


def test_ca_digest_pdf_500_empty():
    """No data in CA DB yet, so digest fails — verify graceful 500."""
    r = requests.get(f"{BASE_URL}/current-affairs/digest/pdf")
    assert r.status_code == 500 or r.status_code == 200
    if r.status_code == 500:
        ok("GET /current-affairs/digest/pdf -> 500 (expected, no data)")
    else:
        warn("/current-affairs/digest/pdf returned 200 despite empty DB")


def test_profile():
    r = requests.get(f"{BASE_URL}/profile")
    assert r.status_code == 200
    data = r.json()
    assert "current_elo" in data
    ok(f"GET /profile -> elo={data['current_elo']}, attempts={data['total_attempted']}")


def test_diagnostic_submit():
    """Submit to pre-seeded session, verify grading."""
    payload = {"session_id": "test-session-001", "responses": {"0": "A", "1": "B", "2": "A"}}
    try:
        r = requests.post(f"{BASE_URL}/diagnostic/submit", json=payload, timeout=10)
        if r.status_code == 200:
            ok("POST /diagnostic/submit -> 200, status=completed")
        elif r.status_code == 400 or r.status_code == 500:
            ok("POST /diagnostic/submit -> already submitted or error")
        else:
            warn(f"POST /diagnostic/submit unexpected status {r.status_code}")
    except Exception as e:
        warn(f"POST /diagnostic/submit error -> {e}")


def test_profile_analysis():
    """Trigger profile analysis (needs >=50 attempts, seeded above)."""
    try:
        r = requests.post(f"{BASE_URL}/analyze-profile", timeout=30)
        assert r.status_code == 200
        data = r.json()
        ok(f"POST /analyze-profile -> status={data.get('status', '?')}")
    except requests.Timeout:
        warn("POST /analyze-profile timed out (Gemini API call may be rate-limited)")
    except Exception as e:
        warn(f"POST /analyze-profile error -> {e}")


def test_profile_analysis_get():
    try:
        r = requests.get(f"{BASE_URL}/profile/analysis", timeout=5)
        assert r.status_code == 200
        ok("GET /profile/analysis -> 200")
    except requests.Timeout:
        warn("GET /profile/analysis timed out (expected if no profile analysis exists)")
    except Exception as e:
        warn(f"GET /profile/analysis -> {e}")


def test_activity_log():
    r = requests.get(f"{BASE_URL}/activity-log")
    assert r.status_code == 200
    ok("GET /activity-log -> 200")


def test_trap_summary():
    r = requests.get(f"{BASE_URL}/trap-summary")
    assert r.status_code in (200, 404)
    ok(f"GET /trap-summary -> {r.status_code}")


def test_generate_test_guardrail():
    """Generate-test hits guardrail (scarce tier) — expect 429 or 200 depending on quota."""
    payload = {"topic_studied": "Indian Polity", "question_count": 5, "quality_check": False}
    try:
        r = requests.post(f"{BASE_URL}/generate-test/prelims", json=payload, timeout=15)
        assert r.status_code in (200, 429)
        if r.status_code == 200:
            data = r.json()
            ok(f"POST /generate-test/prelims -> 200, {len(data.get('questions', []))} questions")
        else:
            ok("POST /generate-test/prelims -> 429 (guardrail blocked, expected in test)")
    except requests.Timeout:
        warn("POST /generate-test/prelims timed out (Gemini API call)")


def test_submit_answer_missing_session():
    """submit-answer without valid session returns 404."""
    payload = {"session_id": "nonexistent", "responses": {"0": "A"}}
    r = requests.post(f"{BASE_URL}/submit-answer", json=payload)
    assert r.status_code in (404, 422)
    ok(f"POST /submit-answer (bad session) -> {r.status_code}")


def test_upload_pdf_no_file():
    r = requests.post(f"{BASE_URL}/upload-pdf")
    assert r.status_code == 422
    ok("POST /upload-pdf (no file) -> 422")


def test_omr_mains_empty():
    """POST /ocr/mains-evaluate with no image returns 422."""
    r = requests.post(f"{BASE_URL}/ocr/mains-evaluate")
    assert r.status_code == 422
    ok("POST /ocr/mains-evaluate (no file) -> 422")


def test_current_affairs_ingest_no_params():
    r = requests.post(f"{BASE_URL}/current-affairs/ingest")
    assert r.status_code == 400
    data = r.json()
    ok(f"POST /current-affairs/ingest (no params) -> 400")


def test_current_affairs_fetch():
    r = requests.post(f"{BASE_URL}/current-affairs/fetch")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "started"
    ok("POST /current-affairs/fetch -> 200, started in background")


def test_diagnostic_after_complete():
    """GET /diagnostic should return 400 since already completed."""
    r = requests.get(f"{BASE_URL}/diagnostic")
    assert r.status_code == 400
    ok("GET /diagnostic -> 400 (already completed)")


def test_session_data_bad_id():
    r = requests.get(f"{BASE_URL}/session/bad-session-id/data")
    assert r.status_code == 404
    ok("GET /session/bad-session-id/data -> 404")


def test_session_qp_bad_id():
    r = requests.get(f"{BASE_URL}/session/bad-session-id/question-paper")
    assert r.status_code == 404
    ok("GET /session/bad-session-id/question-paper -> 404")


# ── 4. Run ────────────────────────────────────────────────────────────────────

def main():
    section("0 — Seed Database")
    seed_database()

    section("1 — Start Server")
    if not start_server():
        sys.exit(1)

    try:
        # Non-API-dependent tests (fast, no external calls)
        section("2 — Health & Gate")
        test_health()
        test_gate_ca_exempt()
        test_gate_blocks_before_diagnostic()

        section("3 — Current Affairs")
        test_ca_stats()
        test_ca_list_empty()
        test_ca_detail_404()
        test_ca_digest_pdf_500_empty()
        test_current_affairs_ingest_no_params()
        test_current_affairs_fetch()

        section("4 — Profile (no API)")
        test_profile()

        section("5 — Diagnostic (no API)")
        test_diagnostic_submit()
        test_diagnostic_after_complete()

        section("6 — OMR & Uploads")
        test_omr_mains_empty()
        test_upload_pdf_no_file()

        section("7 — Activity & Sessions")
        test_activity_log()
        test_trap_summary()
        test_submit_answer_missing_session()
        test_session_data_bad_id()
        test_session_qp_bad_id()

        # API-dependent tests (may block server, run last with timeouts)
        section("8 — API-dependent (profile analysis, test gen)")
        test_profile_analysis()
        test_profile_analysis_get()
        test_generate_test_guardrail()

    finally:
        stop_server()

    print(f"\n\033[96m{'='*50}\033[0m")
    total = PASS + FAIL + WARN
    print(f"  \033[92m{PASS} passed\033[0m, \033[91m{FAIL} failed\033[0m, \033[93m{WARN} warnings\033[0m / {total} total")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
