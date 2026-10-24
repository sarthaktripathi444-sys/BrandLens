# test_api.py
# Runs the whole workflow through the real API (login -> rule book -> content -> review -> reviewer decision).
# Needs the packages from requirements.txt (fastapi, httpx). Uses an in-memory database, so nothing is saved.

import json
import os
from pathlib import Path

os.environ["USE_MEMORY_DB"] = "1"       # must be set BEFORE the app is imported
os.environ["GEMINI_API_KEY"] = ""       # force the built-in rules so the test never calls the AI

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)
SAMPLES = Path(__file__).resolve().parents[2] / "sample_data"


def login(role):
    reply = client.post("/auth/login", json={"role": role, "name": role.title()})
    assert reply.status_code == 200
    return {"Authorization": "Bearer " + reply.json()["token"]}


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_login_is_required():
    assert client.get("/content").status_code == 401


def test_full_workflow():
    manager, creator, reviewer = login("manager"), login("creator"), login("reviewer")

    # 1. Only the manager can save the rule book.
    rulebook = json.loads((SAMPLES / "rulebook_sample.json").read_text(encoding="utf-8"))
    assert client.post("/rulebook", json=rulebook, headers=creator).status_code == 403
    assert client.post("/rulebook", json=rulebook, headers=manager).status_code == 200
    assert client.get("/rulebook/active", headers=creator).json()["company"] == "NovaCart"

    # 2. The creator submits content and runs the review.
    text = (SAMPLES / "content_samples" / "email_sample.txt").read_text(encoding="utf-8")
    created = client.post("/content", json={"title": "Email", "type": "Email", "text": text}, headers=creator)
    assert created.status_code == 201
    cid = created.json()["id"]

    review = client.post(f"/review/{cid}/run", headers=creator).json()
    assert review["status"] == "reviewed" and review["findings"] and review["score"] < 100

    # 3. Sending is blocked until every issue is decided.
    assert client.post(f"/review/{cid}/send", headers=creator).status_code == 400
    for finding in review["findings"]:
        reply = client.patch(
            f"/review/{cid}/findings/{finding['id']}", json={"status": "accepted"}, headers=creator
        )
        assert reply.status_code == 200
    assert "14,000" in reply.json()["revised_text"]

    assert client.post(f"/review/{cid}/send", headers=creator).json()["status"] == "pending_review"

    # 4. The reviewer needs a comment to request changes, and can approve.
    bad = client.post(f"/review/{cid}/decision", json={"decision": "changes_requested"}, headers=reviewer)
    assert bad.status_code == 400
    assert client.post(f"/review/{cid}/decision", json={"decision": "approved"}, headers=creator).status_code == 403
    done = client.post(f"/review/{cid}/decision", json={"decision": "approved"}, headers=reviewer)
    assert done.status_code == 200 and done.json()["status"] == "approved"
