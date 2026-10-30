# review.py
# The review workflow. Every URL uses the CONTENT id (one content item has one current review).
#
#   POST  /review/{id}/run                              creator   run the AI review (again, if wanted)
#   GET   /review/{id}                                  anyone    read the review
#   PATCH /review/{id}/findings/{finding_id}            creator   accept or reject one suggested fix with replacement
#   POST  /review/{id}/findings/{finding_id}/alternatives creator generate more compliant rewrites
#   POST  /review/{id}/send                             creator   send to the reviewer (all issues decided)
#   POST  /review/{id}/decision                         reviewer  approve, or request changes with a comment

import hashlib
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.database import contents, reviews, rulebooks
from app.routes.auth import get_current_user, require_role
from app.schemas.review import DecisionIn, FindingStatusIn, ReviewOut, RunReviewIn
from app.services import audit_service, rewrite_service
from app.services import review_service as svc

router = APIRouter(prefix="/review", tags=["review"])


def _get_content(content_id: str):
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


def _get_review(content_id: str):
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
        text = svc.revised_text(text, previous["findings"])  # keep accepted fixes, then check again

    # Execute all checks with channel awareness
    findings, score, meta = svc.run_checks(text, rulebook, content["type"])
    stamp = svc.now()

    contents.update_one(
        {"id": content_id},
        {"$set": {"text": text, "status": "reviewed", "score": score, "updated_at": stamp}},
    )
    review = {"content_id": content_id, "findings": findings, "comment": None, "reviewed_by": None, "created_at": stamp}
    reviews.replace_one({"content_id": content_id}, dict(review), upsert=True)

    # Feature 3: Log review_run event into cryptographic audit ledger
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    audit_service.log_event(
        content_id=content_id,
        action="review_run",
        actor=user,
        details={
            "rulebook_id": rulebook.get("rulebook_id", ""),
            "rulebook_version": rulebook.get("version", 0),
            "score": score,
            "findings_count": len(findings),
            "meta": meta,
            "text_hash": text_hash,
        },
    )

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

    updated_finding = svc.set_finding_status(review, finding_id, body.status, body.replacement)
    reviews.update_one({"content_id": content_id}, {"$set": {"findings": review["findings"]}})

    # Feature 3: Log finding_decided event into cryptographic audit ledger
    audit_service.log_event(
        content_id=content_id,
        action="finding_decided",
        actor=user,
        details={
            "finding_id": finding_id,
            "status": body.status,
            "replacement": body.replacement or updated_finding.get("replacement"),
            "category": updated_finding.get("category"),
            "original_text": updated_finding.get("text"),
        },
    )

    return _response(content, review)


@router.post("/{content_id}/findings/{finding_id}/alternatives")
def get_alternatives(
    content_id: str,
    finding_id: str,
    user=Depends(require_role("creator")),
):
    """
    Feature 2: Generate 2-3 compliant alternative rewrites for a finding on demand.
    Each candidate rewrite is verified against terminology & claim rules before return.
    """
    content = _get_content(content_id)
    review = _get_review(content_id)
    rulebook = rulebooks.find_one({"active": True}, {"_id": 0}) or {}

    target = None
    for f in review.get("findings", []):
        if f["id"] == finding_id:
            target = f
            break

    if not target:
        raise HTTPException(status_code=404, detail="Finding not found.")

    alternatives = rewrite_service.generate_alternatives(
        finding=target,
        full_text=content["text"],
        rulebook=rulebook,
        content_type=content.get("type", "Blog"),
    )

    target["alternatives"] = alternatives
    reviews.update_one({"content_id": content_id}, {"$set": {"findings": review["findings"]}})

    return {"alternatives": alternatives}


@router.post("/{content_id}/send", response_model=ReviewOut)
def send_to_reviewer(content_id: str, user=Depends(require_role("creator"))):
    content = _get_content(content_id)
    review = _get_review(content_id)
    svc.check_can_send(content, review)

    contents.update_one({"id": content_id}, {"$set": {"status": "pending_review", "updated_at": svc.now()}})

    # Feature 3: Log sent_to_reviewer event
    accepted_cnt = len([f for f in review["findings"] if f.get("status") == "accepted"])
    rejected_cnt = len([f for f in review["findings"] if f.get("status") == "rejected"])
    audit_service.log_event(
        content_id=content_id,
        action="sent_to_reviewer",
        actor=user,
        details={
            "accepted_count": accepted_cnt,
            "rejected_count": rejected_cnt,
        },
    )

    return _response(_get_content(content_id), review)


@router.post("/{content_id}/decision", response_model=ReviewOut)
def decide(content_id: str, body: DecisionIn, user=Depends(require_role("reviewer"))):
    content = _get_content(content_id)
    review = _get_review(content_id)
    svc.check_can_decide(content, body.decision, body.comment)

    revised_final = svc.revised_text(content["text"], review["findings"])
    changes = {"status": body.decision, "updated_at": svc.now()}
    if body.decision == "approved":
        changes["final_text"] = revised_final

    contents.update_one({"id": content_id}, {"$set": changes})
    reviews.update_one(
        {"content_id": content_id},
        {"$set": {"comment": body.comment.strip() or None, "reviewed_by": user["name"]}},
    )

    review["comment"] = body.comment.strip() or None
    review["reviewed_by"] = user["name"]

    # Feature 3: Log decision_made event with final text hash
    final_hash = hashlib.sha256(revised_final.encode("utf-8")).hexdigest()
    audit_service.log_event(
        content_id=content_id,
        action="decision_made",
        actor=user,
        details={
            "decision": body.decision,
            "comment": body.comment,
            "final_text_hash": final_hash,
        },
    )

    return _response(_get_content(content_id), review)
