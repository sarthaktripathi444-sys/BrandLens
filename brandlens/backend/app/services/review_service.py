# review_service.py
# The "brain" of a review: runs the multi-layer checks, scores content, and enforces workflow rules.
# Works on plain dictionaries (no database, no web code), so it is easy to test.

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services import llm_client
from app.services.channel_checker import check_channel
from app.services.claim_checker import check_claims
from app.services.fact_checker import check_facts
from app.services.suggestion_engine import apply_accepted, remove_overlaps
from app.services.terminology_checker import check_terminology
from app.services.tone_checker import check_tone

# Points deducted from 100 for each finding category.
PENALTY = {"terminology": 4, "tone": 6, "fact": 10, "claim": 10, "channel": 5}


class WorkflowError(Exception):
    """A request that breaks workflow rules. status is the HTTP status code to answer with."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safely(name: str, failed: List[str], check, *args) -> List[Dict[str, Any]]:
    """Run one checker; if it crashes, log it, add its name to failed, carry on."""
    try:
        return check(*args)
    except Exception as error:
        print(f"[review_service] The {name} check failed and was skipped: {type(error).__name__}: {error}")
        failed.append(name)
        return []


def compute_score(findings: List[Dict[str, Any]]) -> int:
    """100 minus the penalty for every finding, never below 0."""
    return max(0, 100 - sum(PENALTY.get(f.get("category", ""), 5) for f in findings))


def run_checks(text: str, rulebook: Dict[str, Any], content_type: str = "Blog"):
    """
    Execute all compliance checkers in parallel:
    Facts, Claims (channel-aware), Terminology, Tone (channel-aware), and Channel format constraints.
    Returns (findings, score, meta).
    meta = {"ai_used": bool, "checks_failed": [names]}
    """
    failed: List[str] = []
    found: List[Dict[str, Any]] = []

    channel_rules = rulebook.get("channel_rules", {})

    found += _safely("fact", failed, check_facts, text, rulebook.get("facts", []))
    found += _safely("claims", failed, check_claims, text, rulebook.get("claims_policy", ""), content_type, channel_rules)
    found += _safely("terminology", failed, check_terminology, text, rulebook.get("restricted_terms", []))
    found += _safely("tone", failed, check_tone, text, rulebook.get("tone", []), content_type, channel_rules)
    found += _safely("channel", failed, check_channel, text, channel_rules, content_type)

    findings = remove_overlaps(found)
    for number, finding in enumerate(findings, start=1):
        finding["id"] = f"f{number}"
        finding["status"] = "pending"

    meta = {"ai_used": llm_client.is_configured(), "checks_failed": failed}
    return findings, compute_score(findings), meta


def revised_text(text: str, findings: List[Dict[str, Any]]) -> str:
    """The content with every accepted fix applied using backward offset patching."""
    return apply_accepted(text, findings)


def set_finding_status(
    review: Dict[str, Any],
    finding_id: str,
    status: str,
    replacement: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Accept, reject or reset one finding inside a review document.
    If status is accepted, sets the chosen replacement text (or defaults to suggestion).
    """
    for finding in review["findings"]:
        if finding["id"] == finding_id:
            finding["status"] = status
            if replacement is not None:
                finding["replacement"] = replacement
            elif status == "accepted" and not finding.get("replacement"):
                finding["replacement"] = finding.get("suggestion", "")
            return finding
    raise WorkflowError("That issue does not exist in this review.", 404)


def pending_count(review: Dict[str, Any]) -> int:
    return sum(1 for f in review["findings"] if f.get("status") == "pending")


def check_can_edit_review(content: Dict[str, Any]) -> None:
    """The creator may only change decisions while content is in 'reviewed' or 'changes_requested' status."""
    if content["status"] not in ("reviewed", "changes_requested"):
        raise WorkflowError(
            f"This content is '{content['status']}', so its issues can no longer be changed. "
            "Re-run the review to start again."
        )


def check_can_rerun(content: Dict[str, Any]) -> None:
    if content["status"] in ("pending_review", "approved"):
        raise WorkflowError(f"This content is already '{content['status']}' and cannot be reviewed again.", 409)


def check_can_send(content: Dict[str, Any], review: Dict[str, Any]) -> None:
    if content["status"] not in ("reviewed", "changes_requested"):
        raise WorkflowError(f"Only reviewed content can be sent (this one is '{content['status']}').", 409)
    left = pending_count(review)
    if left:
        raise WorkflowError(f"Accept or reject the remaining {left} issue(s) before sending.")


def check_can_decide(content: Dict[str, Any], decision: str, comment: str) -> None:
    if content["status"] != "pending_review":
        raise WorkflowError(f"This content is '{content['status']}', not waiting for review.", 409)
    if decision == "changes_requested" and not (comment or "").strip():
        raise WorkflowError("Please write what needs to change.")
