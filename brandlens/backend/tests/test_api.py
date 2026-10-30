# test_api.py
# Runs the whole workflow (rule book -> content -> review -> reviewer decision).
# Uses an in-memory database, so nothing is saved.

import json
import os
from pathlib import Path
import pytest

os.environ["USE_MEMORY_DB"] = "1"       # must be set BEFORE the app is imported
os.environ["GEMINI_API_KEY"] = ""       # force the built-in rules so the test never calls the AI

from fastapi import HTTPException
from app.services.review_service import WorkflowError
from app.main import health
from app.routes.auth import get_current_user
from app.routes.rulebook import save_rulebook, get_active_rulebook
from app.routes.content import create_content
from app.routes.review import run_review, send_to_reviewer, update_finding, decide
from app.schemas.rulebook import Rulebook
from app.schemas.content import ContentCreate
from app.schemas.review import FindingStatusIn, DecisionIn

SAMPLES = Path(__file__).resolve().parents[2] / "sample_data"


def test_health():
    assert health() == {"status": "ok"}


def test_login_is_required():
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(authorization=None)
    assert exc_info.value.status_code == 401


def test_full_workflow():
    manager = {"name": "Manager", "role": "manager"}
    creator = {"name": "Creator", "role": "creator"}
    reviewer = {"name": "Reviewer", "role": "reviewer"}

    # 1. Save the rule book.
    rulebook_raw = json.loads((SAMPLES / "rulebook_sample.json").read_text(encoding="utf-8"))
    rb_obj = Rulebook(**rulebook_raw)
    saved = save_rulebook(rb_obj, user=manager)
    assert saved["company"] == "NovaCart"
    assert get_active_rulebook(user=creator)["company"] == "NovaCart"

    # 2. The creator submits content and runs the review.
    text = (SAMPLES / "content_samples" / "email_sample.txt").read_text(encoding="utf-8")
    created = create_content(ContentCreate(title="Email", type="Email", text=text), user=creator)
    cid = created["id"]

    review = run_review(cid, user=creator)
    assert review["status"] == "reviewed" and review["findings"] and review["score"] < 100

    # 3. Sending is blocked until every issue is decided.
    with pytest.raises((HTTPException, WorkflowError)) as exc_info:
        send_to_reviewer(cid, user=creator)
    code = getattr(exc_info.value, "status_code", getattr(exc_info.value, "status", None))
    assert code == 400

    reply = None
    for finding in review["findings"]:
        reply = update_finding(cid, finding["id"], FindingStatusIn(status="accepted"), user=creator)
        assert reply["status"] == "reviewed"
    assert "14,000" in reply["revised_text"]

    sent = send_to_reviewer(cid, user=creator)
    assert sent["status"] == "pending_review"

    # 4. The reviewer needs a comment to request changes, and can approve.
    with pytest.raises((HTTPException, WorkflowError)) as exc_info:
        decide(cid, DecisionIn(decision="changes_requested"), user=reviewer)
    code = getattr(exc_info.value, "status_code", getattr(exc_info.value, "status", None))
    assert code == 400

    from app.routes.auth import require_role
    with pytest.raises(HTTPException) as exc_info:
        require_role("reviewer")(creator)
    assert exc_info.value.status_code == 403

    done = decide(cid, DecisionIn(decision="approved"), user=reviewer)
    assert done["status"] == "approved"


def test_rulebook_keeps_the_new_fields_and_gets_a_version():
    manager = {"name": "Manager", "role": "manager"}
    rulebook_raw = json.loads((SAMPLES / "rulebook_sample.json").read_text(encoding="utf-8"))
    rulebook_raw["approved_messaging"] = [{"text": "Built for growing retailers", "context": "product pages"}]
    rulebook_raw["channel_rules"] = {"Ad": {"max_chars": 120, "required_disclaimer": "Terms apply."}}
    rb_obj = Rulebook(**rulebook_raw)
    saved = save_rulebook(rb_obj, user=manager)
    assert saved["approved_messaging"][0]["text"] == "Built for growing retailers"
    assert saved["channel_rules"]["Ad"]["max_chars"] == 120
    assert "rulebook_id" in saved and "version" in saved

    active = get_active_rulebook(user=manager)
    assert active["approved_messaging"][0]["text"] == "Built for growing retailers"
    assert active["channel_rules"]["Ad"]["max_chars"] == 120
    assert "rulebook_id" in active and "version" in active


def test_ad_is_an_accepted_content_type():
    creator = {"name": "Creator", "role": "creator"}
    reply = create_content(ContentCreate(title="Ad", type="Ad", text="Buy now."), user=creator)
    assert reply["type"] == "Ad"
