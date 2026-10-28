AUDIT_ACTIONS = (
    "content_created", "review_run", "finding_decided",
    "sent_to_reviewer", "decision_made", "rulebook_saved",
)


def log_event(content_id, action, actor, details=None):
    """actor = the user dict from get_current_user: {"name", "role"}. Stub: does nothing yet."""
    return None


def get_trail(content_id):
    """All events for one content item, oldest first. Stub: returns []."""
    return []


def verify_chain(events):
    """Stub raises on purpose: returning True would let a certificate say
    'chain verified' with nothing checked."""
    raise NotImplementedError("audit_service.verify_chain is not written yet (Person B)")