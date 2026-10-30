from test_api import client, login

from app.services.audit_service import get_trail, hash_text, verify_chain


def test_creating_content_is_logged():
    creator = login("creator")
    reply = client.post(
        "/content",
        json={"title": "Launch", "type": "Ad", "text": "Buy now."},
        headers=creator,
    )
    assert reply.status_code == 201
    trail = get_trail(reply.json()["id"])
    assert [event["action"] for event in trail] == ["content_created"]
    assert trail[0]["actor"] == "Creator"
    assert trail[0]["details"]["text_hash"] == hash_text("Buy now.")
    assert verify_chain(trail) is True