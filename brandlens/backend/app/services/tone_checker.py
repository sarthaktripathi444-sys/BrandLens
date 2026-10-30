# tone_checker.py
# Checks whether the writing matches the brand tone.
# With a Gemini key: the AI judges tone sentence by sentence (prompts/tone_prompt.txt) considering channel context.
# Without a key (or if the AI fails): a channel-aware built-in list of hype phrases is used instead.

import re
from typing import Any, Dict, List, Optional

from app.services import llm_client
from app.services.suggestion_engine import make_finding

# Base fallback rules: (regex, replacement, issue title, list of alternative rewrites).
BASE_HYPE_RULES = [
    (r"\bare\s+obsessed\s+with\b", "value", "Over-excited wording", ["appreciate", "focus on", "prioritize"]),
    (r"\bobsessed\b", "enthusiastic", "Over-excited wording", ["committed", "dedicated", "passionate"]),
    (r"\bDon['\u2019]t\s+miss\s+out\b\s*[-\u2013\u2014:]\s*", "Discover ", "Pushy, pressure-style wording", ["Explore ", "Learn more: ", "Check out "]),
    (r"\bchanges\s+everything\s+about\s+how\b", "changes how", "Exaggerated wording", ["improves how", "updates how", "transforms how"]),
    (r"\b(?:amazing|incredible|mind-blowing|unbelievable)\b", "strong", "Hype-filled wording", ["effective", "compelling", "noteworthy"]),
]


def _rule_based(
    text: str,
    tone: List[str],
    content_type: str = "Blog",
    channel_rules: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    reason = f"The brand tone is {', '.join(tone)}; hype or pressure wording does not fit it."
    rule = "Brand tone: " + (", ".join(tone) if tone else "professional")
    findings = []
    is_social = content_type.lower() in ("social", "social post")

    # Exclamation mark rules: social copy permits a single exclamation mark; formal channels flag exclamation marks
    if is_social:
        excl_pattern = r"!{3,}"
        excl_issue = "Excessive exclamation marks"
    else:
        excl_pattern = r"!{2,}"
        excl_issue = "Multiple exclamation marks"

    for m in re.finditer(excl_pattern, text):
        findings.append(
            make_finding(
                category="tone",
                text=m.group(0),
                start=m.start(),
                end=m.end(),
                issue=excl_issue,
                reason="Multiple exclamation marks appear unprofessional and overly excited.",
                rule=rule,
                suggestion="!" if is_social else ".",
                alternatives=["." if is_social else "!"],
            )
        )

    for pattern, replacement, issue, alts in BASE_HYPE_RULES:
        for m in re.finditer(pattern, text, flags=re.IGNORECASE):
            findings.append(
                make_finding(
                    category="tone",
                    text=m.group(0),
                    start=m.start(),
                    end=m.end(),
                    issue=issue,
                    reason=reason,
                    rule=rule,
                    suggestion=replacement,
                    alternatives=alts,
                )
            )

    return findings


def _clean_replacement(quote: str, raw_suggestion: str, alternatives: List[str]) -> str:
    """Ensure the suggestion is a clean drop-in replacement phrase, not instructional advice."""
    s = (raw_suggestion or "").strip()
    ADVICE_PATTERNS = r"^(?:focus on|replace\b|remove\b|avoid\b|use\b|consider\b|state\b|rephrase\b|ensure\b|do not\b|never\b|delete\b)"
    if not re.search(ADVICE_PATTERNS, s, re.I):
        return s

    for alt in alternatives:
        if alt and not re.search(ADVICE_PATTERNS, alt, re.I) and len(alt.split()) <= len(quote.split()) + 6:
            return alt

    lower_q = quote.lower().strip()
    if lower_q.startswith("are obsessed with"):
        return "love"
    elif "don't miss out" in lower_q or "dont miss out" in lower_q:
        return "Discover "
    return s


def _ai_based(
    text: str,
    tone: List[str],
    content_type: str = "Blog",
    channel_rules: Optional[Dict[str, Any]] = None,
) -> Optional[List[Dict[str, Any]]]:
    """Returns a list of findings, or None if the AI could not be used (so caller falls back)."""
    if not llm_client.is_configured():
        return None

    # Determine channel guidance
    channel_guidance = ""
    if channel_rules and content_type in channel_rules:
        c_rule = channel_rules[content_type]
        if hasattr(c_rule, "tone_notes"):
            channel_guidance = c_rule.tone_notes
        elif isinstance(c_rule, dict):
            channel_guidance = c_rule.get("tone_notes", "")

    if not channel_guidance:
        if content_type.lower() in ("social", "social post"):
            channel_guidance = "Engaging, conversational and approachable, while avoiding spammy hype or excessive emojis/exclamations."
        elif content_type.lower() in ("press release", "news"):
            channel_guidance = "Strictly factual, objective, authoritative, and restrained. Zero informal idioms or hyperbole."
        elif content_type.lower() in ("ad", "landing page"):
            channel_guidance = "Clear, value-driven and direct without unsubstantiated superlatives or manipulative urgency."
        else:
            channel_guidance = "Clear, professional, and aligned with company brand identity."

    try:
        items = llm_client.ask_for_findings(
            "tone_prompt.txt",
            tone=", ".join(tone),
            channel=content_type,
            channel_guidance=channel_guidance,
            text=text,
        )
    except llm_client.LLMError as error:
        print(f"[tone_checker] AI skipped, using built-in rules: {error}")
        return None

    findings = []
    for item in items:
        quote = str(item.get("text", "")).strip()
        start = text.find(quote) if quote else -1
        if start == -1:
            continue

        raw_alts = item.get("alternatives")
        alts = [str(a).strip() for a in raw_alts if str(a).strip()] if isinstance(raw_alts, list) else []

        clean_sugg = _clean_replacement(quote, str(item.get("suggestion") or ""), alts)

        findings.append(
            make_finding(
                category="tone",
                text=quote,
                start=start,
                end=start + len(quote),
                issue=str(item.get("issue") or "Off-brand tone"),
                reason=str(item.get("reason") or ""),
                rule=str(item.get("rule") or f"{content_type} tone: " + ", ".join(tone)),
                suggestion=clean_sugg,
                alternatives=alts,
                source="ai",
            )
        )
    return findings


def check_tone(
    text: str,
    tone: List[str],
    content_type: str = "Blog",
    channel_rules: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Check brand voice and tone against guidelines with channel-adaptive sensitivity.
    """
    ai_findings = _ai_based(text, tone, content_type, channel_rules)
    return ai_findings if ai_findings is not None else _rule_based(text, tone, content_type, channel_rules)
