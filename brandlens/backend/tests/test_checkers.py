# test_checkers.py
# Quick tests that the checkers catch the mistakes planted in sample_data.
# Run from the backend folder with:  python -m pytest tests -v
# These tests need no database, no web server and no AI key.

import json
from pathlib import Path

from app.services.fact_checker import check_facts
from app.services.review_service import run_checks, revised_text
from app.services.terminology_checker import check_terminology

SAMPLES = Path(__file__).resolve().parents[2] / "sample_data"
RULEBOOK = json.loads((SAMPLES / "rulebook_sample.json").read_text(encoding="utf-8"))


def sample(name):
    return (SAMPLES / "content_samples" / name).read_text(encoding="utf-8").strip()


def categories(findings):
    return {f["category"] for f in findings}


def test_users_gets_a_terminology_flag_with_plural_replacement():
    findings = check_terminology("Our users love it.", RULEBOOK["restricted_terms"])
    assert len(findings) == 1
    assert findings[0]["text"] == "users"
    assert findings[0]["suggestion"] == "customers"


def test_terminology_matches_whole_words_only():
    assert check_terminology("A superuser and a username.", RULEBOOK["restricted_terms"]) == []


def test_wrong_customer_count_gets_a_fact_flag():
    findings = check_facts("We have 50000 customers.", RULEBOOK["facts"])
    assert len(findings) == 1 and findings[0]["suggestion"] == "14,000"


def test_correct_numbers_and_safe_ranges_are_not_flagged():
    text = "We have 14,000 customers, more than 10,000 customers, and were founded in 2019."
    assert check_facts(text, RULEBOOK["facts"]) == []


def test_wrong_founding_year_gets_a_fact_flag():
    findings = check_facts("We have been helping retailers since 2015.", RULEBOOK["facts"])
    assert [f["suggestion"] for f in findings] == ["2019"]


def test_blog_sample_triggers_every_kind_of_check():
    findings, score, _ = run_checks(sample("blog_sample.txt"), RULEBOOK)
    assert {"claim", "fact", "terminology", "tone"} <= categories(findings)
    assert score < 60


def test_every_planted_sample_gets_flagged():
    for name in ("blog_sample.txt", "email_sample.txt", "press_release_sample.txt", "social_post_sample.txt"):
        findings, score, _ = run_checks(sample(name), RULEBOOK)
        assert findings, name
        assert score < 100, name


def test_findings_never_overlap_and_fixes_do_not_corrupt_text():
    for name in ("blog_sample.txt", "email_sample.txt", "press_release_sample.txt", "social_post_sample.txt"):
        text = sample(name)
        findings, _, _ = run_checks(text, RULEBOOK)
        spans = sorted((f["start"], f["end"]) for f in findings)
        assert all(a_end <= b_start for (_, a_end), (b_start, _) in zip(spans, spans[1:]))
        for f in findings:
            assert text[f["start"]:f["end"]] == f["text"]
            f["status"] = "accepted"
        fixed = revised_text(text, findings)
        assert "50,000" not in fixed and "50000" not in fixed


def test_after_accepting_all_fixes_a_second_review_is_clean_of_facts_and_terms():
    text = sample("email_sample.txt")
    findings, _, _ = run_checks(text, RULEBOOK)
    for f in findings:
        f["status"] = "accepted"
    again, _ = run_checks(revised_text(text, findings), RULEBOOK)
    assert categories(again) <= {"claim", "tone"} and len(again) == 0


def test_sign_off_best_is_not_a_claim():
    findings, _, _ = run_checks("Thanks for reading.\n\nBest,\nThe Team", RULEBOOK)
    assert findings == []

def test_run_checks_returns_meta_and_accepts_a_content_type():
    findings, score, meta = run_checks("Our users love it.", RULEBOOK, "Ad")
    assert findings and set(meta) == {"ai_used", "checks_failed"}
    assert meta["checks_failed"] == []


def test_a_crashing_checker_is_reported_in_meta(monkeypatch):
    import app.services.review_service as svc

    def boom(*args):
        raise RuntimeError("broken")

    monkeypatch.setattr(svc, "check_tone", boom)
    _, _, meta = run_checks("Our users love it.", RULEBOOK)
    assert meta["checks_failed"] == ["tone"]
