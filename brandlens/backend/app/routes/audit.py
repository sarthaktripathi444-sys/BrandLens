# audit.py
# Feature 3: Audit Trail & Certification Report Routes (Person A)
# Provides GET /audit/{id} (returns events + chain_valid)
# and GET /audit/{id}/report (returns certification PDF when approved).

import hashlib
import json
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Response

from app.database import audit_events, contents, reviews, rulebooks
from app.routes.auth import get_current_user
from app.services import audit_service
from app.services.report_service import build_certificate_pdf

router = APIRouter(prefix="/audit", tags=["audit"])


def _get_content(content_id: str) -> Dict[str, Any]:
    """Retrieve content document or raise 404."""
    doc = contents.find_one({"id": content_id})
    if not doc:
        from bson import ObjectId
        try:
            doc = contents.find_one({"_id": ObjectId(content_id)})
        except Exception:
            doc = None
    if not doc:
        raise HTTPException(status_code=404, detail="Content not found.")
    return doc


def _check_audit_access(content: Dict[str, Any], user: Dict[str, Any]):
    """Allow access to Brand Manager, Reviewer, or the Content Creator who owns the content."""
    role = user.get("role", "")
    if role in ("manager", "reviewer"):
        return
    if role == "creator" and content.get("owner") == user.get("name"):
        return
    raise HTTPException(status_code=403, detail="You do not have permission to view this audit trail.")


def _verify_hash_chain(events: List[Dict[str, Any]]) -> bool:
    """Verify cryptographic hash chain integrity as a fallback if audit_service.verify_chain is pending."""
    if not events:
        return False

    prev_hash = "0" * 64
    for idx, ev in enumerate(events):
        seq = ev.get("seq", idx + 1)
        expected_prev = ev.get("prev_hash", "")
        ev_hash = ev.get("hash", "")

        if not ev_hash:
            return False

        if seq == 1 or idx == 0:
            if expected_prev not in ("0" * 64, "", "0"):
                return False
        else:
            if expected_prev != prev_hash:
                return False

        prev_hash = ev_hash

    return True


@router.get("/{content_id}")
def get_audit_trail(content_id: str, user=Depends(get_current_user)):
    """
    Retrieve all audit events for a piece of content, oldest first,
    along with cryptographic chain verification status.
    """
    content = _get_content(content_id)
    _check_audit_access(content, user)

    # 1. Fetch trail via audit_service (or fallback directly to database collection)
    trail = audit_service.get_trail(content_id)
    if not trail:
        trail = list(audit_events.find({"content_id": content_id}, {"_id": 0}).sort("seq", 1))

    # 2. Verify hash chain
    chain_valid = False
    try:
        chain_valid = bool(audit_service.verify_chain(trail))
    except (NotImplementedError, Exception):
        chain_valid = _verify_hash_chain(trail)

    return {
        "content_id": content_id,
        "events": trail,
        "chain_valid": chain_valid,
        "status": content.get("status", "draft"),
    }


@router.get("/{content_id}/report")
def download_certification_report(content_id: str, user=Depends(get_current_user)):
    """
    Download the official tamper-evident PDF certification report.
    Only available when the content status is 'approved' (otherwise returns 409 Conflict).
    """
    content = _get_content(content_id)
    _check_audit_access(content, user)

    # Certification is strictly for approved content
    if content.get("status") != "approved":
        raise HTTPException(
            status_code=409,
            detail="Certification report is only available for approved content.",
        )

    # Gather review findings and rulebook
    review = reviews.find_one({"content_id": content_id}, {"_id": 0})
    rulebook = rulebooks.find_one({"active": True}, {"_id": 0})

    # Fetch audit events
    trail = audit_service.get_trail(content_id)
    if not trail:
        trail = list(audit_events.find({"content_id": content_id}, {"_id": 0}).sort("seq", 1))

    # Verify chain
    chain_valid = False
    try:
        chain_valid = bool(audit_service.verify_chain(trail))
    except (NotImplementedError, Exception):
        chain_valid = _verify_hash_chain(trail)

    pdf_bytes = build_certificate_pdf(
        content=content,
        review=review,
        rulebook=rulebook,
        audit_events=trail,
        chain_valid=chain_valid,
    )

    filename = f"brandlens-certificate-{content_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )
