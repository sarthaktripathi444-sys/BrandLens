from test_api import SAMPLES, client, login

from app.services.audit_service import get_trail, verify_chain
import json


def test_whole_review_flow_is_logged_in_order():
    manager, creator, reviewer = login("manager"), login("creator"), login("reviewer")
    rulebook = json.loads((SAMPLES / "rulebook_sample.json").read_text(encoding="utf-8"))
    client.post("/rulebook", json=rulebook, headers=manager)

    text = (SAMPLES / "content_samples" / "email_sample.txt").read_text(encoding="utf-8")
    created = client.post("/content", json={"title": "Email", "type": "Email", "text": text}, headers=creator)
    cid = created.json()["id"]

    review = client.post(f"/review/{cid}/run", headers=creator).json()
    for finding in review["findings"]:
        client.patch(f"/review/{cid}/findings/{finding['id']}", json={"status": "accepted"}, headers=creator)
    assert client.post(f"/review/{cid}/send", headers=creator).status_code == 200
    decision = client.post(
        f"/review/{cid}/decision", json={"decision": "approved", "comment": "Looks good."}, headers=reviewer
    )
    assert decision.status_code == 200

    trail = get_trail(cid)
    actions = [event["action"] for event in trail]
    expected = ["content_created", "review_run"] + ["finding_decided"] * len(review["findings"]) + [
        "sent_to_reviewer",
        "decision_made",
    ]
    assert actions == expected
    assert verify_chain(trail) is True