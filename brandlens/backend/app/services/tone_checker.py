# tone_checker.py
# Checks whether the writing matches the brand tone.
# With a Gemini key: the AI judges tone sentence by sentence (prompts/tone_prompt.txt).
# Without a key (or if the AI fails): a small built-in list of hype phrases is used instead, so the demo never breaks.

import re

from app.services import llm_client
from app.services.suggestion_engine import make_finding

# Fallback rules: (regex, replacement, issue title).
HYPE_RULES = [
    (r"!{2,}", ".", "Too many exclamation marks"),
    (r"\bare\s+obsessed\s+with\b", "value", "Over-excited wording"),
    (r"\bobsessed\b", "enthusiastic", "Over-excited wording"),
    (r"\bDon['\u2019]t\s+miss\s+out\b\s*[-\u2013\u2014:]\s*", "Discover ", "Pushy, pressure-style wording"),
    (r"\bchanges\s+everything\s+about\s+how\b", "changes how", "Exaggerated wording"),
    (r"\b(?:amazing|incredible|mind-blowing|unbelievable)\b", "strong", "Hype-filled wording"),
]


def _rule_based(text, tone):
    reason = f"The brand tone is {', '.join(tone)}; hype or pressure wording does not fit it."
    rule = "Brand tone: " + (", ".join(tone) if tone else "professional")
    findings = []
    for pattern, replacement, issue in HYPE_RULES:
        for m in re.finditer(pattern, text, flags=re.IGNORECASE):
            findings.append(
                make_finding("tone", m.group(0), m.start(), m.end(), issue, reason, rule, replacement)
            )
    return findings


def _ai_based(text, tone):
    """Returns a list of findings, or None if the AI could not be used (so the caller can fall back)."""
    if not llm_client.is_configured():
        return None
    try:
        items = llm_client.ask_for_findings("tone_prompt.txt", tone=", ".join(tone), text=text)
    except llm_client.LLMError as error:
        print(f"[tone_checker] AI skipped, using built-in rules: {error}")
        return None

    findings = []
    for item in items:
        quote = str(item.get("text", "")).strip()
        start = text.find(quote) if quote else -1
        if start == -1:
            continue
        findings.append(
            make_finding(
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
        )
    return findings


def check_tone(text, tone):
    """tone is the list of tone words from the rule book, e.g. ["professional", "trustworthy"]."""
    ai_findings = _ai_based(text, tone)
    return ai_findings if ai_findings is not None else _rule_based(text, tone)
