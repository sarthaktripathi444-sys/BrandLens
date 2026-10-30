# audit_service.py
# Feature 3: Cryptographic Audit Trail & Event Logging Service (Person B)
# Sequences all content actions (creation, review, triage decisions, approvals)
# into an immutable SHA-256 block ledger with prev_hash pointers.

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.database import audit_events

AUDIT_ACTIONS = (
    "content_created",
    "review_run",
    "finding_decided",
    "sent_to_reviewer",
    "decision_made",
    "rulebook_saved",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_repr(data: Any) -> str:
    """Deterministic JSON string for hashing."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def compute_event_hash(
    content_id: str,
    seq: int,
    prev_hash: str,
    action: str,
    actor_name: str,
    actor_role: str,
    timestamp: str,
    details: Dict[str, Any],
) -> str:
    """Calculate the deterministic SHA-256 block hash for an audit event."""
    payload = f"{content_id}:{seq}:{prev_hash}:{action}:{actor_name}:{actor_role}:{timestamp}:{_canonical_repr(details or {})}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def log_event(
    content_id: str,
    action: str,
    actor: Any,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Log an event to the audit trail with sequence number and SHA-256 prev_hash linking.
    actor can be a user dict {"name", "role"} or a string.
    """
    if details is None:
        details = {}

    # Normalize actor
    if isinstance(actor, dict):
        actor_name = actor.get("name") or "System"
        actor_role = actor.get("role") or "system"
    elif isinstance(actor, str):
        actor_name = actor
        actor_role = "user"
    else:
        actor_name = "System"
        actor_role = "system"

    actor_dict = {"name": actor_name, "role": actor_role}

    # Find the last event for this content to determine seq and prev_hash
    last_event = audit_events.find_one({"content_id": content_id}, sort=[("seq", -1)])
    if last_event:
        raw_seq = last_event.get("seq", 0)
        try:
            seq = int(raw_seq) + 1
        except (ValueError, TypeError):
            seq = 1
        prev_hash = last_event.get("hash", "0" * 64)
    else:
        seq = 1
        prev_hash = "0" * 64

    timestamp = _now()
    ev_hash = compute_event_hash(
        content_id=content_id,
        seq=seq,
        prev_hash=prev_hash,
        action=action,
        actor_name=actor_name,
        actor_role=actor_role,
        timestamp=timestamp,
        details=details,
    )

    doc = {
        "content_id": content_id,
        "seq": seq,
        "action": action,
        "actor": actor_dict,
        "timestamp": timestamp,
        "details": details,
        "prev_hash": prev_hash,
        "hash": ev_hash,
    }

    audit_events.insert_one(doc)
    doc.pop("_id", None)
    return doc


def get_trail(content_id: str) -> List[Dict[str, Any]]:
    """Retrieve all audit events for a content item, oldest first."""
    return list(audit_events.find({"content_id": content_id}, {"_id": 0}).sort("seq", 1))


def verify_chain(events: List[Dict[str, Any]]) -> bool:
    """
    Verify the cryptographic hash chain of an audit trail.
    Validates sequential numbering, prev_hash continuity, and SHA-256 block hashes.
    """
    if not events:
        return False

    prev_hash = "0" * 64
    for idx, ev in enumerate(events):
        seq = ev.get("seq", idx + 1)
        expected_seq = idx + 1
        ev_prev = ev.get("prev_hash", "")
        ev_hash = ev.get("hash", "")

        # Sequence must be continuous starting at 1
        if seq != expected_seq:
            return False

        # Previous hash must link correctly
        if ev_prev != prev_hash:
            return False

        # Recalculate hash
        actor = ev.get("actor") or {}
        if isinstance(actor, dict):
            actor_name = actor.get("name", "System")
            actor_role = actor.get("role", "system")
        else:
            actor_name = str(actor)
            actor_role = "user"

        recalculated = compute_event_hash(
            content_id=ev.get("content_id", ""),
            seq=seq,
            prev_hash=ev_prev,
            action=ev.get("action", ""),
            actor_name=actor_name,
            actor_role=actor_role,
            timestamp=ev.get("timestamp", ""),
            details=ev.get("details", {}),
        )

        if recalculated != ev_hash:
            return False

        prev_hash = ev_hash

    return True
