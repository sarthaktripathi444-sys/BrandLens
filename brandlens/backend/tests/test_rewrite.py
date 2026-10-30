import pytest

import app.services.rewrite_service as rs
from app.services import review_service as svc
from app.services.suggestion_engine import apply_accepted

TEXT = "Try our cheap plan."
RULEBOOK = {
    "tone": [],
    "restricted_terms": [{"term": "cheap", "use": "affordable", "reason": "Sounds low quality"}],
}


def make_review():
    finding = {
        "id": "f1", "category": "terminology", "text": "cheap plan", "start": 8, "end": 18,
        "suggestion": "affordable plan", "alternatives": ["affordable plan", "value plan"],
        "status": "pending",
    }
    return {"findings": [finding]}


def test_chosen_alternative_is_applied_to_the_text():
    review = make_review()
    svc.set_finding_status(review, "f1", "accepted", "value plan")
    assert review["findings"][0]["replacement"] == "value plan"
    assert apply_accepted(TEXT, review["findings"]) == "Try our value plan."


def test_accepting_without_a_choice_uses_the_suggestion():
    review = make_review()
    svc.set_finding_status(review, "f1", "accepted")
    assert apply_accepted(TEXT, review["findings"]) == "Try our affordable plan."


def test_a_replacement_that_is_not_an_alternative_is_refused():
    review = make_review()
    with pytest.raises(svc.WorkflowError):
        svc.set_finding_status(review, "f1", "accepted", "something I typed")


def test_rejecting_clears_the_chosen_replacement():
    review = make_review()
    svc.set_finding_status(review, "f1", "accepted", "value plan")
    svc.set_finding_status(review, "f1", "rejected")
    assert review["findings"][0]["replacement"] is None


def test_suggest_more_drops_duplicates_and_rule_breakers(monkeypatch):
    monkeypatch.setattr(rs.llm_client, "is_configured", lambda: True)
    monkeypatch.setattr(rs.llm_client, "ask_for_findings", lambda *a, **k: [
        {"text": "low-cost plan"},    # fine
        {"text": "cheap deal"},       # still uses the restricted word, so it is dropped
        {"text": "affordable plan"},  # already offered, so it is dropped
    ])
    fresh = rs.suggest_more(make_review()["findings"][0], TEXT, RULEBOOK, "Blog")
    assert fresh == ["low-cost plan"]