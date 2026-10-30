from app.services.channel_checker import check_channel
from app.services.review_service import revised_text, run_checks


def issues(findings):
    return [finding["issue"] for finding in findings]


def test_no_rules_means_no_findings():
    assert check_channel("Buy now!!", "Ad", {}) == []
    assert check_channel("Buy now!!", "Ad", {"Email": {"allow_exclamation": False}}) == []


def test_ad_rules_flag_length_exclamation_and_missing_disclaimer():
    rules = {"Ad": {"max_chars": 20, "allow_exclamation": False, "required_disclaimer": "Terms apply."}}
    found = issues(check_channel("Buy our planner today! Sale ends soon", "Ad", rules))
    assert any("Too long" in issue for issue in found)
    assert any("Exclamation" in issue for issue in found)
    assert any("disclaimer" in issue for issue in found)


def test_disclaimer_present_is_not_flagged():
    rules = {"Ad": {"required_disclaimer": "Terms apply."}}
    assert check_channel("Buy now. Terms apply.", "Ad", rules) == []


def test_email_subject_too_long():
    rules = {"Email": {"max_subject_chars": 20}}
    found = check_channel("Subject: This subject line is far too long\nHello", "Email", rules)
    assert len(found) == 1 and found[0]["text"].startswith("This subject")


def test_extra_hashtags_are_flagged():
    rules = {"Social Post": {"max_hashtags": 2}}
    found = check_channel("Love it #a #b #c #d", "Social Post", rules)
    assert [finding["text"] for finding in found] == ["#c", "#d"]


def test_accepting_the_exclamation_fix_changes_the_text():
    rules = {"Ad": {"allow_exclamation": False}}
    found = check_channel("Wow!", "Ad", rules)
    found[0]["status"] = "accepted"
    assert revised_text("Wow!", found) == "Wow."


def test_run_checks_includes_channel_findings():
    rulebook = {"tone": [], "channel_rules": {"Ad": {"allow_exclamation": False}}}
    findings, _, meta = run_checks("Buy now!", rulebook, "Ad")
    assert any("Channel rule" in finding["rule"] for finding in findings)
    assert meta["checks_failed"] == []