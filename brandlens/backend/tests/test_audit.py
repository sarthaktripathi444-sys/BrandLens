# test_audit.py
# Unit and integration tests for Feature 3: Audit Trail & Certification Report (Person A)

import hashlib
import json
import os
import pytest

os.environ["USE_MEMORY_DB"] = "1"
os.environ["GEMINI_API_KEY"] = ""

from fastapi import HTTPException
from app.database import contents, reviews, rulebooks, audit_events
from app.routes.audit import get_audit_trail, download_certification_report, _verify_hash_chain
from app.routes.auth import login, LoginIn
from app.services.report_service import build_certificate_pdf, compute_text_hash


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

    user = {"name": "Alice", "role": "creator"}
    data = get_audit_trail(content_id, user=user)
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

    user = {"name": "Alice", "role": "creator"}
    with pytest.raises(HTTPException) as exc_info:
        get_audit_trail(content_id, user=user)
    assert exc_info.value.status_code == 403
    assert "permission" in exc_info.value.detail.lower()


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
    res_mgr = get_audit_trail(content_id, user={"name": "Chief Officer", "role": "manager"})
    assert res_mgr["content_id"] == content_id

    # Reviewer allowed
    res_rev = get_audit_trail(content_id, user={"name": "Reviewer Rob", "role": "reviewer"})
    assert res_rev["content_id"] == content_id


def test_get_audit_trail_not_found():
    with pytest.raises(HTTPException) as exc_info:
        get_audit_trail("non_existent_id_99999", user={"name": "Manager", "role": "manager"})
    assert exc_info.value.status_code == 404


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

    with pytest.raises(HTTPException) as exc_info:
        download_certification_report(content_id, user={"name": "Alice", "role": "creator"})
    assert exc_info.value.status_code == 409
    assert "approved" in exc_info.value.detail.lower()


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

    res = download_certification_report(content_id, user={"name": "Alice", "role": "creator"})
    assert res.media_type == "application/pdf"
    assert "brandlens-certificate" in res.headers["Content-Disposition"]
    assert res.body.startswith(b"%PDF-")


def test_login_endpoint():
    res = login(LoginIn(role="creator", name="Alice"))
    assert res["role"] == "creator"
    assert res["name"] == "Alice"
    assert "token" in res
