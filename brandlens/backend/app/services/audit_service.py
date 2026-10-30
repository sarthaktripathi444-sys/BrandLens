"""Audit trail: an append-only log of what happens to a piece of content.

Every event is chained to the one before it with SHA-256, so editing an old
event is detectable (tamper-evident, not tamper-proof).

Event shape:
  content_id, seq, ts, actor, role, action, details, prev_hash, hash
"""
import hashlib
import json
from datetime import datetime, timezone

from app.database import audit_events

AUDIT_ACTIONS = (
    "content_created", "review_run", "finding_decided",
    "sent_to_reviewer", "decision_made", "rulebook_saved",
)

GENESIS = "0" * 64  # prev_hash of the first event


def hash_text(text):
    """SHA-256 of a piece of text (used to prove which text was approved)."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _event_hash(event):
    body = {key: event.get(key) for key in
            ("content_id", "seq", "ts", "actor", "role", "action", "details")}
    payload = event["prev_hash"] + json.dumps(
        body, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_trail(content_id):
    """All events for one content item, oldest first."""
    events = list(audit_events.find({"content_id": content_id}, {"_id": 0}))
    events.sort(key=lambda event: event["seq"])
    return events


def log_event(content_id, action, actor, details=None):
    """actor = the user dict from get_current_user: {"name", "role"}.
    Never raises: a logging problem must not break the main workflow."""
    try:
        if action not in AUDIT_ACTIONS:
            print(f"[audit_service] Unknown action: {action}")
        actor = actor or {}
        trail = get_trail(content_id)
        event = {
            "content_id": content_id,
            "seq": len(trail) + 1,
            "ts": datetime.now(timezone.utc).isoformat(),
            "actor": actor.get("name", "unknown"),
            "role": actor.get("role", "unknown"),
            "action": action,
            "details": details or {},
            "prev_hash": trail[-1]["hash"] if trail else GENESIS,
        }
        event["hash"] = _event_hash(event)
        audit_events.insert_one(dict(event))
        return event
    except Exception as error:
        print(f"[audit_service] Could not log {action}: {type(error).__name__}: {error}")
        return None


def verify_chain(events):
    """True only if every event is numbered, linked and unedited."""
    previous = GENESIS
    for expected_seq, event in enumerate(events, start=1):
        if event.get("seq") != expected_seq:
            return False
        if event.get("prev_hash") != previous:
            return False
        if event.get("hash") != _event_hash(event):
            return False
        previous = event["hash"]
    return True