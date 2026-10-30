# rewrite_service.py
# Creates MORE rewrites for one finding on demand (the "Suggest more rewrites" button).
# Every rewrite is re-checked against the built-in rules; any that would break a rule is dropped.

from app.services import llm_client
from app.services.channel_checker import channel_guidance, check_channel
from app.services.claim_checker import _rule_based as claim_rules
from app.services.fact_checker import check_facts
from app.services.terminology_checker import check_terminology
from app.services.tone_checker import _rule_based as tone_rules

MAX_ALTERNATIVES = 6  # most alternatives one finding can hold


def _rule_findings(text, rulebook, content_type):
    """All built-in (no AI) findings for this text. Fast, so we can test many candidates."""
    channel_rules = rulebook.get("channel_rules", {})
    found = []
    found += check_facts(text, rulebook.get("facts", []))
    found += claim_rules(text, rulebook.get("claims_policy", ""), content_type)
    found += check_terminology(text, rulebook.get("restricted_terms", []))
    found += tone_rules(text, rulebook.get("tone", []), content_type, channel_rules)
    found += check_channel(text, content_type, channel_rules)
    return found


def _is_clean(text, finding, candidate, rulebook, content_type):
    """True if putting `candidate` in place of the flagged text creates no new finding on that spot."""
    start, end = finding["start"], finding["end"]
    new_text = text[:start] + candidate + text[end:]
    new_end = start + len(candidate)
    for f in _rule_findings(new_text, rulebook, content_type):
        if isinstance(f.get("start"), int) and f["start"] < new_end and f["end"] > start:
            return False
    return True


def suggest_more(finding, text, rulebook, content_type):
    """Returns a list of NEW, rule-checked rewrites (may be empty). Raises llm_client.LLMError if the AI fails."""
    if not isinstance(finding.get("start"), int) or not isinstance(finding.get("end"), int):
        return []

    already = [finding.get("suggestion", "")] + list(finding.get("alternatives") or [])
    seen = {a.strip().lower() for a in already if a} | {finding.get("text", "").strip().lower()}

    start, end = finding["start"], finding["end"]
    items = llm_client.ask_for_findings(
        "rewrite_prompt.txt",
        brand_tone=", ".join(rulebook.get("tone", [])),
        channel=content_type,
        channel_guidance=channel_guidance(content_type, rulebook.get("channel_rules", {})),
        issue=finding.get("issue", ""),
        reason=finding.get("reason", ""),
        rule=finding.get("rule", ""),
        flagged=finding.get("text", ""),
        context=text[max(0, start - 200): end + 200],
        already_offered=" | ".join(a for a in already if a) or "(none)",
    )

    room = max(0, MAX_ALTERNATIVES - len([a for a in already if a]))
    fresh = []
    for item in items:
        candidate = str(item.get("text", "")).strip()
        if not candidate or candidate.lower() in seen:
            continue
        if not _is_clean(text, finding, candidate, rulebook, content_type):
            continue
        seen.add(candidate.lower())
        fresh.append(candidate)
        if len(fresh) >= room:
            break
    return fresh