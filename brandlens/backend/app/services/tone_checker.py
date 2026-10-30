# tone_checker.py
# Checks whether the writing matches the brand tone (and the channel's tone rules).
# With a Gemini key: the AI judges tone sentence by sentence (prompts/tone_prompt.txt).
# Without a key (or if the AI fails): a small built-in list of hype phrases is used instead, so the demo never breaks.

import re

from app.services import llm_client
from app.services.channel_checker import add_alternatives, channel_guidance
from app.services.suggestion_engine import make_finding

EXCLAMATIONS = r"!{2,}"

# Fallback rules: (regex, replacement, issue title, extra alternatives).
HYPE_RULES = [
    (EXCLAMATIONS, ".", "Too many exclamation marks", []),
    (r"\bare\s+obsessed\s+with\b", "value", "Over-excited wording", ["appreciate", "enjoy"]),
    (r"\bobsessed\b", "enthusiastic", "Over-excited wording", ["keen", "passionate"]),
    (r"\bDon['\u2019]t\s+miss\s+out\b\s*[-\u2013\u2014:]\s*", "Discover ", "Pushy, pressure-style wording", ["Explore ", "See "]),
    (r"\bchanges\s+everything\s+about\s+how\b", "changes how", "Exaggerated wording", ["improves how", "supports how"]),
    (r"\b(?:amazing|incredible|mind-blowing|unbelievable)\b", "strong", "Hype-filled wording", ["solid", "reliable"]),
]


def _rule_based(text, tone, content_type="Blog", channel_rules=None):
    reason = f"The brand tone is {', '.join(tone)}; hype or pressure wording does not fit it."
    rule = "Brand tone: " + (", ".join(tone) if tone else "professional")
    channel_rule = (channel_rules or {}).get(content_type)
    one_allowed = isinstance(channel_rule, dict) and channel_rule.get("allow_exclamation") is True

    findings = []
    for pattern, replacement, issue, extras in HYPE_RULES:
        if pattern == EXCLAMATIONS and one_allowed:
            replacement, extras = "!", ["."]  # this channel allows one exclamation mark
        for m in re.finditer(pattern, text, flags=re.IGNORECASE):
            finding = make_finding("tone", m.group(0), m.start(), m.end(), issue, reason, rule, replacement)
            findings.append(add_alternatives(finding, extras))
    return findings


def _ai_based(text, tone, content_type="Blog", channel_rules=None):
    """Returns a list of findings, or None if the AI could not be used (so the caller can fall back)."""
    if not llm_client.is_configured():
        return None
    try:
        items = llm_client.ask_for_findings(
            "tone_prompt.txt",
            tone=", ".join(tone),
            channel=content_type,
            channel_guidance=channel_guidance(content_type, channel_rules),
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
        finding = make_finding(
            "tone",
            quote,
            start,
            start + len(quote),
            str(item.get("issue") or "Off-brand tone"),
            str(item.get("reason") or ""),
            str(item.get("rule") or "Brand tone: " + ", ".join(tone)),
            str(item.get("suggestion") or ""),
            source="ai",
        )
        extras = item.get("alternatives")
        findings.append(add_alternatives(finding, extras if isinstance(extras, list) else []))
    return findings


def check_tone(text, tone, content_type="Blog", channel_rules=None):
    """tone is the list of tone words from the rule book, e.g. ["professional", "trustworthy"]."""
    ai_findings = _ai_based(text, tone, content_type, channel_rules)
    return ai_findings if ai_findings is not None else _rule_based(text, tone, content_type, channel_rules)