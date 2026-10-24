# review_service.py
# The "brain" of a review: runs the four checks, scores the content and enforces the workflow rules.
# It works on plain dictionaries (no database, no web code), so it is easy to test.

from datetime import datetime, timezone

from app.services.claim_checker import check_claims
from app.services.fact_checker import check_facts
from app.services.suggestion_engine import apply_accepted, remove_overlaps
from app.services.terminology_checker import check_terminology
from app.services.tone_checker import check_tone

# Points taken off the score of 100 for each finding.
PENALTY = {"terminology": 4, "tone": 6, "fact": 10, "claim": 10}


class WorkflowError(Exception):
    """A request that breaks the workflow rules. `status` is the HTTP status code to answer with."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def now():
    return datetime.now(timezone.utc).isoformat()


def _safely(name, check, *args):
    """Run one checker; if it crashes, report it in the server log and carry on with the others."""
    try:
        return check(*args)
    except Exception as error:
        print(f"[review_service] The {name} check failed and was skipped: {type(error).__name__}: {error}")
        return []


def compute_score(findings):
    """100 minus the penalty for every finding, never below 0."""
    return max(0, 100 - sum(PENALTY.get(f["category"], 5) for f in findings))


def run_checks(text, rulebook):
    """Run all four checks on the text. Returns (findings, score)."""
    found = []
    found += _safely("fact", check_facts, text, rulebook.get("facts", []))
    found += _safely("claims", check_claims, text, rulebook.get("claims_policy", ""))
    found += _safely("terminology", check_terminology, text, rulebook.get("restricted_terms", []))
    found += _safely("tone", check_tone, text, rulebook.get("tone", []))

    findings = remove_overlaps(found)
    for number, finding in enumerate(findings, start=1):
        finding["id"] = f"f{number}"
        finding["status"] = "pending"

    return findings, compute_score(findings)


def revised_text(text, findings):
    """The content with every accepted fix applied."""
    return apply_accepted(text, findings)


def set_finding_status(review, finding_id, status):
    """Accept, reject or reset one finding inside a review document."""
    for finding in review["findings"]:
        if finding["id"] == finding_id:
            finding["status"] = status
            return finding
    raise WorkflowError("That issue does not exist in this review.", 404)


def pending_count(review):
    return sum(1 for f in review["findings"] if f["status"] == "pending")


def check_can_edit_review(content):
    """The creator may only change decisions while the content is in 'reviewed' status."""
    if content["status"] != "reviewed":
        raise WorkflowError(
            f"This content is '{content['status']}', so its issues can no longer be changed. "
            "Re-run the review to start again."
        )


def check_can_rerun(content):
    if content["status"] in ("pending_review", "approved"):
        raise WorkflowError(f"This content is already '{content['status']}' and cannot be reviewed again.", 409)


def check_can_send(content, review):
    if content["status"] != "reviewed":
        raise WorkflowError(f"Only AI-reviewed content can be sent (this one is '{content['status']}').", 409)
    left = pending_count(review)
    if left:
        raise WorkflowError(f"Accept or reject the remaining {left} issue(s) before sending.")


def check_can_decide(content, decision, comment):
    if content["status"] != "pending_review":
        raise WorkflowError(f"This content is '{content['status']}', not waiting for review.", 409)
    if decision == "changes_requested" and not (comment or "").strip():
        raise WorkflowError("Please write what needs to change.")
