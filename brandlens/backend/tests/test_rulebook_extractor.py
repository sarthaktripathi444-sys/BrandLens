# test_rulebook_extractor.py
# Tests for Feature 1: Automated Brand Rulebook Extractor (Person A)

import io
import json
import os
from unittest.mock import patch
import pytest

os.environ["USE_MEMORY_DB"] = "1"
os.environ["GEMINI_API_KEY"] = ""

from app.schemas.rulebook import Rulebook
from app.routes.rulebook import save_rulebook, get_active_rulebook
from app.services.rulebook_extractor import (
    validate_url,
    html_to_text,
    chunk_text,
    merge_results,
    extract_rulebook_from_text,
    check_schema_guidance,
    ExtractError,
)


# 1. URL Guard and Validation Tests
def test_validate_url_rejects_non_http():
    with pytest.raises(ExtractError, match="Only http and https"):
        validate_url("ftp://example.com/file.txt")
    with pytest.raises(ExtractError, match="Only http and https"):
        validate_url("file:///etc/passwd")


def test_validate_url_rejects_localhost():
    with pytest.raises(ExtractError, match="blocked for security"):
        validate_url("http://localhost:8000/guidelines")
    with pytest.raises(ExtractError):
        validate_url("http://127.0.0.1:8000/guidelines")


def test_validate_url_rejects_private_ips():
    with pytest.raises(ExtractError, match="Private, local, or internal"):
        validate_url("http://192.168.1.1/guidelines")
    with pytest.raises(ExtractError, match="Private, local, or internal"):
        validate_url("http://10.0.0.1/guidelines")


# 2. HTML to Text
def test_html_to_text():
    html = """
    <html>
      <head><title>Brand Guidelines</title><style>.hidden { display: none; }</style></head>
      <body>
        <nav><a href="/">Home</a></nav>
        <script>console.log("secret");</script>
        <h1>Acme Corp Guidelines</h1>
        <p>Our tone is innovative and bold.</p>
        <footer>Copyright 2026</footer>
      </body>
    </html>
    """
    text = html_to_text(html)
    assert "Acme Corp Guidelines" in text
    assert "Our tone is innovative and bold." in text
    assert "console.log" not in text
    assert "Home" not in text
    assert "Copyright" not in text


# 3. Chunking
def test_chunk_text():
    short_text = "This is a short brand guideline."
    chunks = chunk_text(short_text, chunk_size=100)
    assert len(chunks) == 1
    assert chunks[0] == short_text

    long_paras = "\n\n".join([f"Paragraph {i}: " + ("content " * 20) for i in range(10)])
    chunks = chunk_text(long_paras, chunk_size=200)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c) > 0


# 4. Merging and Deduping
def test_merge_results():
    part1 = {
        "company": "Acme",
        "tone": ["bold", "innovative"],
        "restricted_terms": [{"term": "cheap", "use": "affordable", "reason": "sounds bad", "source_quote": "q1"}],
        "facts": [{"label": "founded", "value": "2020", "source_quote": "q2"}],
    }
    part2 = {
        "company": "Acme",
        "tone": ["bold", "friendly"],
        "restricted_terms": [{"term": "cheap", "use": "affordable", "reason": "sounds bad", "source_quote": "q1"}],
        "facts": [{"label": "customers", "value": "5000", "source_quote": "q3"}],
    }
    merged = merge_results([part1, part2])
    assert merged["company"] == "Acme"
    assert set(merged["tone"]) == {"bold", "innovative", "friendly"}
    assert len(merged["restricted_terms"]) == 1
    assert len(merged["facts"]) == 2


# 5. Quote Verification ("never trust the AI blindly") and Fact Warnings
def test_never_trust_ai_blindly_drops_ungrounded_items():
    source_text = "Acme was founded in 2020. Never say cheap, always say affordable."
    ai_output = {
        "company": "Acme",
        "tone": ["trustworthy"],
        "restricted_terms": [
            {"term": "cheap", "use": "affordable", "reason": "cheap is bad", "source_quote": "Never say cheap, always say affordable"},
            {"term": "untrusted", "use": "trusted", "reason": "hallucinated", "source_quote": "this quote is not in the text"},
        ],
        "facts": [
            {"label": "founded", "value": 2020, "source_quote": "founded in 2020"},
            {"label": "revenue", "value": "$10M", "source_quote": "revenue was 10 million dollars"},
        ],
        "approved_messaging": [
            {"text": "Fake slogan", "source_quote": "slogan that does not exist"}
        ],
    }

    with patch("app.services.llm_client.is_configured", return_value=True), patch(
        "app.services.llm_client.ask_for_json", return_value=ai_output
    ):
        rulebook, warnings, _ = extract_rulebook_from_text(source_text, source_name="test.txt")

    # The ungrounded restricted term, fact, and message should be dropped
    assert len(rulebook.restricted_terms) == 1
    assert rulebook.restricted_terms[0].term == "cheap"
    assert len(rulebook.facts) == 1
    assert rulebook.facts[0].label == "founded"
    assert len(rulebook.approved_messaging) == 0

    # Warnings should mention the remaining fact and the dropped items
    assert any("founded" in w for w in warnings)
    assert any("Dropped" in w for w in warnings)


# 6. Fallback Rule-Based Extraction Without API Key
def test_rule_based_fallback_extraction_without_key():
    source = """
    NovaCart Official Brand Guidelines
    About Us: NovaCart was founded in 2019. We serve over 14,000 active customers.
    Our tone is professional and friendly but factual.
    Do not describe products as "cheap". Use "affordable" instead.
    No unsupported superlatives or guaranteed results.
    Tagline: "Built for growing retailers"
    """
    rulebook, warnings, _ = extract_rulebook_from_text(source, source_name="fallback_test.txt")
    assert rulebook.company == "NovaCart"
    assert "professional" in rulebook.tone
    assert any(r.term == "cheap" for r in rulebook.restricted_terms)
    assert any(f.label == "founded" and f.value == 2019 for f in rulebook.facts)
    assert any("Notice: GEMINI_API_KEY is not configured" in w for w in warnings)


# 7. Rulebook Extraction with Content
def test_extract_with_uploaded_file():
    content = "Acme brand guidelines. Tone is clear and concise. Founded in 2021."

    mock_rulebook = {
        "company": "Acme",
        "tone": ["clear", "concise"],
        "restricted_terms": [],
        "facts": [{"label": "founded", "value": 2021, "source_quote": "Founded in 2021"}],
        "approved_messaging": [],
    }

    with patch("app.services.llm_client.is_configured", return_value=True), patch(
        "app.services.llm_client.ask_for_json", return_value=mock_rulebook
    ):
        rulebook, warnings, _ = extract_rulebook_from_text(content, source_name="guidelines.txt")

    assert rulebook.company == "Acme"
    assert "clear" in rulebook.tone
    assert len(warnings) > 0


# 8. Versioning on Save
def test_save_rulebook_assigns_version_and_id():
    manager = {"name": "Test Manager", "role": "manager"}
    rb = Rulebook(
        company="VersionedTestCo",
        tone=["modern"],
        restricted_terms=[],
        facts=[],
        claims_policy="No false claims.",
    )
    saved1 = save_rulebook(rb, user=manager)
    assert saved1["rulebook_id"] != ""
    v1 = saved1["version"]
    assert v1 >= 1

    # Saving another increments version
    saved2 = save_rulebook(rb, user=manager)
    assert saved2["version"] == v1 + 1
    assert saved2["rulebook_id"] != saved1["rulebook_id"]

    # Active returns the newest
    active = get_active_rulebook(user=manager)
    assert active["version"] == saved2["version"]
    assert active["rulebook_id"] == saved2["rulebook_id"]


# 9. Schema Completeness Guidance
def test_schema_guidance_detects_missing_sections():
    partial = {"company": "Brand", "tone": []}
    guidance = check_schema_guidance(partial)
    assert any("company" in g for g in guidance)
    assert any("tone" in g for g in guidance)
    assert any("restricted_terms" in g for g in guidance)
    assert any("facts" in g for g in guidance)
    assert any("claims_policy" in g for g in guidance)


def test_aurora_pantry_extraction():
    with open("../sample_data/aurora_pantry_guidelines.txt", "r", encoding="utf-8") as f:
        text = f.read()
    rulebook, warnings, _ = extract_rulebook_from_text(text, source_name="aurora_pantry.pdf")
    assert rulebook.company == "Aurora Pantry"
    assert "warm" in rulebook.tone
    assert any(r.term == "user" and r.use == "member" for r in rulebook.restricted_terms)
    assert any(r.term == "cheap" and r.use == "affordable" for r in rulebook.restricted_terms)
    assert any(f.label == "founded" and f.value == 2016 for f in rulebook.facts)
    assert any(f.label == "members" and f.value == 185000 for f in rulebook.facts)
    assert "food, not medicine" in rulebook.claims_policy
    assert "Email" in rulebook.channel_rules
