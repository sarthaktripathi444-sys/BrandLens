import copy
import uuid

from app.services.audit_service import get_trail, log_event, verify_chain

ACTOR = {"name": "Creator", "role": "creator"}


def test_events_are_numbered_and_chained():
    cid = uuid.uuid4().hex
    log_event(cid, "content_created", ACTOR, {"text_hash": "abc"})
    log_event(cid, "review_run", ACTOR, {"score": 80})
    log_event(cid, "sent_to_reviewer", ACTOR)
    trail = get_trail(cid)
    assert [event["seq"] for event in trail] == [1, 2, 3]
    assert trail[1]["prev_hash"] == trail[0]["hash"]
    assert verify_chain(trail) is True


def test_editing_an_event_breaks_the_chain():
    cid = uuid.uuid4().hex
    log_event(cid, "review_run", ACTOR, {"score": 80})
    log_event(cid, "sent_to_reviewer", ACTOR)
    trail = copy.deepcopy(get_trail(cid))
    trail[0]["details"]["score"] = 100
    assert verify_chain(trail) is False