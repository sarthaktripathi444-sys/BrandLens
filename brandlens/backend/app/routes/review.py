# review.py
# The review workflow. Every URL uses the CONTENT id (one content item has one current review).
#
#   POST  /review/{id}/run                    creator   run the AI review (again, if wanted)
#   GET   /review/{id}                        anyone    read the review
#   PATCH /review/{id}/findings/{finding_id}  creator   accept or reject one suggested fix
#   POST  /review/{id}/send                   creator   send to the reviewer (all issues decided)
#   POST  /review/{id}/decision               reviewer  approve, or request changes with a comment

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.database import contents, reviews, rulebooks
from app.routes.auth import get_current_user, require_role
from app.schemas.review import DecisionIn, FindingStatusIn, ReviewOut, RunReviewIn
from app.services import review_service as svc
from app.services.audit_service import hash_text, log_event

router = APIRouter(prefix="/review", tags=["review"])


def _get_content(content_id):
    content = contents.find_one({"id": content_id})
    if not content:
        from bson import ObjectId
        try:
            content = contents.find_one({"_id": ObjectId(content_id)})
        except Exception:
            content = None
    if not content:
        raise HTTPException(status_code=404, detail="Content not found.")
    if not content.get("id") and "_id" in content:
        content["id"] = str(content["_id"])
    if "type" not in content:
        content["type"] = content.get("content_type", "Blog")
    if "_id" in content:
        del content["_id"]
    return content


def _get_review(content_id):
    review = reviews.find_one({"content_id": content_id}, {"_id": 0})
    if not review:
        raise HTTPException(status_code=404, detail="This content has not been reviewed yet.")
    return review


def _response(content, review):
    """Combine the content and its review into the one object the frontend pages use."""
    return {
        "content_id": content["id"],
        "title": content["title"],
        "type": content["type"],
        "text": content["text"],
        "revised_text": svc.revised_text(content["text"], review["findings"]),
        "score": content.get("score"),
        "status": content["status"],
        "findings": review["findings"],
        "comment": review.get("comment"),
        "reviewed_by": review.get("reviewed_by"),
    }


@router.post("/{content_id}/run", response_model=ReviewOut)
def run_review(
    content_id: str,
    body: Optional[RunReviewIn] = None,
    user=Depends(require_role("creator")),
):
    content = _get_content(content_id)
    svc.check_can_rerun(content)

    rulebook = rulebooks.find_one({"active": True}, {"_id": 0})
    if not rulebook:
        raise svc.WorkflowError("There is no active rule book yet. Ask a Brand Manager to upload one first.")

    text = content["text"]
    previous = reviews.find_one({"content_id": content_id}, {"_id": 0})
    if body and body.apply_accepted and previous:
        text = svc.revised_text(text, previous["findings"])  # keep the accepted fixes, then check again

    findings, score, meta = svc.run_checks(text, rulebook, content["type"])
    stamp = svc.now()

    contents.update_one(
        {"id": content_id},
        {"$set": {"text": text, "status": "reviewed", "score": score, "updated_at": stamp}},
    )
    review = {"content_id": content_id, "findings": findings, "comment": None, "reviewed_by": None, "created_at": stamp}
    reviews.replace_one({"content_id": content_id}, dict(review), upsert=True)

    by_category = {}
    for finding in findings:
        category = finding.get("category", "other")
        by_category[category] = by_category.get(category, 0) + 1
    log_event(content_id, "review_run", user, {
        "score": score,
        "finding_count": len(findings),
        "findings_by_category": by_category,
        "rulebook_company": rulebook.get("company"),
        "rulebook_id": rulebook.get("rulebook_id"),
        "rulebook_version": rulebook.get("version"),
        "ai_used": meta["ai_used"],
        "checks_failed": meta["checks_failed"],
        "text_hash": hash_text(text),
        "text_snapshot": text,  # the text is overwritten on re-review, so keep a copy here
    })

    return _response(_get_content(content_id), review)


@router.get("/{content_id}", response_model=ReviewOut)
def read_review(content_id: str, user=Depends(get_current_user)):
    return _response(_get_content(content_id), _get_review(content_id))


@router.patch("/{content_id}/findings/{finding_id}", response_model=ReviewOut)
def update_finding(
    content_id: str,
    finding_id: str,
    body: FindingStatusIn,
    user=Depends(require_role("creator")),
):
    content = _get_content(content_id)
    review = _get_review(content_id)
    svc.check_can_edit_review(content)

    finding = next((f for f in review["findings"] if f.get("id") == finding_id), {})
    before = finding.get("status")
    flagged_text = finding.get("text")
    suggestion = finding.get("suggestion")
    category = finding.get("category")

    svc.set_finding_status(review, finding_id, body.status)
    reviews.update_one({"content_id": content_id}, {"$set": {"findings": review["findings"]}})

    log_event(content_id, "finding_decided", user, {
        "finding_id": finding_id,
        "category": category,
        "text": flagged_text,
        "suggestion": suggestion,
        "before": before,
        "after": body.status,
        "replacement": body.replacement,
    })
    return _response(content, review)


@router.post("/{content_id}/send", response_model=ReviewOut)
def send_to_reviewer(content_id: str, user=Depends(require_role("creator"))):
    content = _get_content(content_id)
    review = _get_review(content_id)
    svc.check_can_send(content, review)

    contents.update_one({"id": content_id}, {"$set": {"status": "pending_review", "updated_at": svc.now()}})

    statuses = [f.get("status") for f in review["findings"]]
    log_event(content_id, "sent_to_reviewer", user, {
        "accepted": statuses.count("accepted"),
        "rejected": statuses.count("rejected"),
    })
    return _response(_get_content(content_id), review)


@router.post("/{content_id}/decision", response_model=ReviewOut)
def decide(content_id: str, body: DecisionIn, user=Depends(require_role("reviewer"))):
    content = _get_content(content_id)
    review = _get_review(content_id)
    svc.check_can_decide(content, body.decision, body.comment)

    changes = {"status": body.decision, "updated_at": svc.now()}
    if body.decision == "approved":
        changes["final_text"] = svc.revised_text(content["text"], review["findings"])
    contents.update_one({"id": content_id}, {"$set": changes})
    reviews.update_one(
        {"content_id": content_id},
        {"$set": {"comment": body.comment.strip() or None, "reviewed_by": user["name"]}},
    )

    review["comment"] = body.comment.strip() or None
    review["reviewed_by"] = user["name"]

    log_event(content_id, "decision_made", user, {
        "decision": body.decision,
        "comment": review["comment"],
        "final_text_hash": hash_text(changes["final_text"]) if "final_text" in changes else None,
    })
    return _response(_get_content(content_id), review)