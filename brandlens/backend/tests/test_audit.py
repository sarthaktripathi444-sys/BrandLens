import copy
import uuid

from app.services.audit_service import get_trail, log_event, verify_chain

ACTOR = {"name": "Creator", "role": "creator"}


def test_events_are_numbered_and_chained():
    cid = uuid.uuid4().hex
    log_event(cid, "content_created", ACTOR, {"text_hash": "abc"})
    log_event(cid, "review_run", ACTOR, {"score": 80})
    log_event(cid, "sent_to_reviewer", ACTOR)
    trail = get_trail(cid)
    assert [event["seq"] for event in trail] == [1, 2, 3]
    assert trail[1]["prev_hash"] == trail[0]["hash"]
    assert verify_chain(trail) is True


def test_editing_an_event_breaks_the_chain():
    cid = uuid.uuid4().hex
    log_event(cid, "review_run", ACTOR, {"score": 80})
    log_event(cid, "sent_to_reviewer", ACTOR)
    trail = copy.deepcopy(get_trail(cid))
    trail[0]["details"]["score"] = 100
    assert verify_chain(trail) is False
# test_audit.py
# Unit and integration tests for Feature 3: Audit Trail & Certification Report (Person A)

import hashlib
import json
import os
import pytest

os.environ["USE_MEMORY_DB"] = "1"
os.environ["GEMINI_API_KEY"] = ""

from fastapi.testclient import TestClient
from app.main import app
from app.database import contents, reviews, rulebooks, audit_events
from app.routes.audit import _verify_hash_chain
from app.services.report_service import build_certificate_pdf, compute_text_hash

client = TestClient(app)


def auth_header(role: str, name: str):
    res = client.post("/auth/login", json={"role": role, "name": name})
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['token']}"}


def make_test_chain(content_id: str, count: int = 3):
    """Generate a valid mock cryptographic audit chain."""
    events = []
    prev_hash = "0" * 64
    for seq in range(1, count + 1):
        payload = f"{content_id}:{seq}:{prev_hash}:action_{seq}"
        ev_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        event = {
            "content_id": content_id,
            "seq": seq,
            "action": "content_created" if seq == 1 else "review_run" if seq == 2 else "decision_made",
            "actor": {"name": "Test User", "role": "creator"},
            "timestamp": "2026-10-29T10:00:00Z",
            "details": {"score": 92} if seq == 2 else {"decision": "approved"} if seq == 3 else {},
            "prev_hash": prev_hash,
            "hash": ev_hash,
        }
        events.append(event)
        prev_hash = ev_hash
    return events


# 1. Hash Chain Integrity Verification
def test_verify_hash_chain_valid():
    events = make_test_chain("cid_123", count=4)
    assert _verify_hash_chain(events) is True


def test_verify_hash_chain_empty():
    assert _verify_hash_chain([]) is False


def test_verify_hash_chain_broken_link():
    events = make_test_chain("cid_123", count=3)
    # Tamper with prev_hash of block 2
    events[1]["prev_hash"] = "altered_hash_12345"
    assert _verify_hash_chain(events) is False


def test_verify_hash_chain_missing_hash():
    events = make_test_chain("cid_123", count=2)
    events[0]["hash"] = ""
    assert _verify_hash_chain(events) is False


# 2. PDF Certificate Generator
def test_build_certificate_pdf_creates_valid_pdf():
    content = {
        "id": "content_abc123",
        "title": "Summer Launch Post",
        "type": "Social Post",
        "text": "Aurora Pantry makes the most delicious organic jams.",
        "status": "approved",
        "owner": "Alice",
        "score": 95,
        "created_at": "2026-10-29T10:00:00Z",
    }
    review = {
        "content_id": "content_abc123",
        "score": 95,
        "status": "approved",
        "findings": [
            {
                "id": "f1",
                "category": "restricted_term",
                "issue": "Prohibited superlative",
                "text": "most delicious",
                "rule": "Avoid unverifiable superlatives",
                "suggestion": "delicious",
                "replacement": "delicious",
                "status": "accepted",
                "decided_by": {"name": "Alice", "role": "creator"},
            },
            {
                "id": "f2",
                "category": "tone",
                "issue": "Tone mismatch",
                "text": "jams",
                "rule": "Use artisanal preserves",
                "suggestion": "artisanal preserves",
                "status": "rejected",
                "decided_by": {"name": "Alice", "role": "creator"},
            },
        ],
    }
    rulebook = {
        "rulebook_id": "rb_001",
        "version": 2,
        "company": "Aurora Pantry",
    }
    audit_events = make_test_chain("content_abc123", count=3)

    pdf_bytes = build_certificate_pdf(
        content=content,
        review=review,
        rulebook=rulebook,
        audit_events=audit_events,
        chain_valid=True,
    )

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF-")


def test_compute_text_hash():
    text = "Hello world"
    expected = hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert compute_text_hash(text) == expected
    assert compute_text_hash("") == hashlib.sha256(b"").hexdigest()


# 3. GET /audit/{id} Authorization & Data Tests
def test_get_audit_trail_creator_owns_content():
    content_id = "test_audit_own_content"
    contents.delete_many({"id": content_id})
    contents.insert_one({
        "id": content_id,
        "title": "My Blog",
        "type": "Blog",
        "text": "Test content",
        "status": "draft",
        "owner": "Alice",
    })

    headers = auth_header("creator", "Alice")
    res = client.get(f"/audit/{content_id}", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["content_id"] == content_id
    assert "events" in data
    assert "chain_valid" in data
    assert data["status"] == "draft"


def test_get_audit_trail_creator_does_not_own_content():
    content_id = "test_audit_other_content"
    contents.delete_many({"id": content_id})
    contents.insert_one({
        "id": content_id,
        "title": "Private Blog",
        "type": "Blog",
        "text": "Test content",
        "status": "draft",
        "owner": "Bob",
    })

    headers = auth_header("creator", "Alice")
    res = client.get(f"/audit/{content_id}", headers=headers)
    assert res.status_code == 403
    assert "permission" in res.json()["detail"].lower()


def test_get_audit_trail_manager_and_reviewer_allowed():
    content_id = "test_audit_team_content"
    contents.delete_many({"id": content_id})
    contents.insert_one({
        "id": content_id,
        "title": "Shared Doc",
        "type": "Press Release",
        "text": "Test content",
        "status": "pending_review",
        "owner": "Bob",
    })

    # Manager allowed
    mgr_headers = auth_header("manager", "Chief Officer")
    res_mgr = client.get(f"/audit/{content_id}", headers=mgr_headers)
    assert res_mgr.status_code == 200

    # Reviewer allowed
    rev_headers = auth_header("reviewer", "Reviewer Rob")
    res_rev = client.get(f"/audit/{content_id}", headers=rev_headers)
    assert res_rev.status_code == 200


def test_get_audit_trail_not_found():
    headers = auth_header("manager", "Manager")
    res = client.get("/audit/non_existent_id_99999", headers=headers)
    assert res.status_code == 404


# 4. GET /audit/{id}/report Tests
def test_download_report_rejected_when_not_approved():
    content_id = "test_unapproved_content"
    contents.delete_many({"id": content_id})
    contents.insert_one({
        "id": content_id,
        "title": "Draft Article",
        "type": "Article",
        "text": "Unapproved text",
        "status": "pending_review",
        "owner": "Alice",
    })

    headers = auth_header("creator", "Alice")
    res = client.get(f"/audit/{content_id}/report", headers=headers)
    assert res.status_code == 409
    assert "approved" in res.json()["detail"].lower()


def test_download_report_success_when_approved():
    content_id = "test_approved_content"
    contents.delete_many({"id": content_id})
    audit_events.delete_many({"content_id": content_id})

    contents.insert_one({
        "id": content_id,
        "title": "Approved Campaign Announcement",
        "type": "Social Post",
        "text": "Official certified text from Aurora Pantry.",
        "status": "approved",
        "owner": "Alice",
        "score": 98,
        "created_at": "2026-10-29T10:00:00Z",
    })

    # Insert mock events into audit_events collection
    events = make_test_chain(content_id, count=3)
    audit_events.insert_many(events)

    headers = auth_header("creator", "Alice")
    res = client.get(f"/audit/{content_id}/report", headers=headers)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert "brandlens-certificate" in res.headers["content-disposition"]
    assert res.content.startswith(b"%PDF-")
