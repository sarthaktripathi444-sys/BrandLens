# claim_checker.py
# Flags promotional claims that need evidence: rankings ("#1", "best"), guaranteed results,
# statistics and "will double your sales" promises.
# Built-in rules always run (so it works without AI). If Gemini is available it adds extra claims it spots.

import re

from app.services import llm_client
from app.services.channel_checker import add_alternatives, channel_guidance
from app.services.suggestion_engine import (
    capitalise_at_sentence_start,
    make_finding,
    plural,
)

# Words that must not be swallowed as part of a noun ("best IN the world", "best FOR you").
STOP = r"(?:in|for|of|and|that|is|on|to|way|with)\b"

# Each rule: (regex, builder that makes the replacement text from the match, issue title, why it needs evidence).
RULES = [
    (
        rf"\b(?:the\s+)?(?:best|leading)\s+(?!{STOP})([\w-]+(?:\s(?!{STOP})[\w-]+)?)"
        r"(?:\s+in\s+(?:the\s+)?(?:industry|market|world|business))?",
        lambda m: f"a trusted {m.group(1)}",
        "Unsupported ranking claim",
        "Superlatives such as best, leading or top need independent evidence.",
    ),
    (
        r"\bthe\s+most\s+(\w+)\s+([\w-]+(?:\s[\w-]+)?)\s+ever\s+(?:built|made|created)",
        lambda m: f"a {m.group(1)} {m.group(2)}",
        "Unsupported superlative",
        '"Most ... ever" cannot be proven.',
    ),
    (
        r"\bthe\s+#\s*1\s+(choice|solution|platform|provider)\b",
        lambda m: f"a trusted {m.group(1)}",
        "Unsupported ranking claim",
        "A #1 ranking needs a named, verifiable source.",
    ),
    (
        r"#\s*1(?:\s+in\s+the\s+(?:world|industry|market|business))?|\bnumber[- ]one(?:\s+in\s+the\s+\w+)?",
        lambda m: "a trusted name",
        "Unsupported ranking claim",
        "A #1 ranking needs a named, verifiable source.",
    ),
    (
        r"\b(?:a\s+|an\s+)?\d[\d,]*(?:\.\d+)?%\s+(?:increase|boost|growth|jump|rise|improvement)\s+in\s+([\w-]+)",
        lambda m: f"an increase in {m.group(1)}",
        "Unsourced statistic",
        "Performance numbers must be backed by evidence.",
    ),
    (
        r"\b(?:double|triple|quadruple)s?\s+(revenue|sales|profits?|growth|conversions?)"
        r"(?:\s+for\s+(?:every|all|each)\s+(\w+))?",
        lambda m: f"help {plural(m.group(2)) if m.group(2) else 'businesses'} grow {m.group(1)}",
        "Guaranteed-result claim",
        "Promising specific results for everyone cannot be guaranteed.",
    ),
    (
        r"\b(?:are|is|will\s+be)\s+guaranteed\s+to\s+(go\s+up|increase|grow)",
        lambda m: f"may {m.group(1)}",
        "Guaranteed-result claim",
        "Outcomes cannot be guaranteed.",
    ),
    (
        r"\b(?:100%\s+)?guaranteed?\s+(results|success|growth|savings)\b",
        lambda m: f"designed to deliver {m.group(1)}",
        "Guaranteed-result claim",
        "Outcomes cannot be guaranteed.",
    ),
    (
        r"\brevolutionary\b|\bgame[- ]chang(?:er|ing)\b",
        lambda m: "innovative",
        "Unsupported superlative",
        "Words like revolutionary are hype without evidence.",
    ),
    (
        r"\bunmatched\b|\bunrivall?ed\b|\bunbeatable\b|\bworld[- ]class\b",
        lambda m: "high-quality",
        "Unsupported superlative",
        "Absolute quality claims need evidence.",
    ),
    (
        r"\b(?:best|leading)\b(?!\s*,|\s+(?:regards|wishes))",  # skips sign-offs like "Best,"
        lambda m: "trusted",
        "Unsupported ranking claim",
        "Superlatives such as best or leading need independent evidence.",
    ),
]
# Extra, stricter rules that only run for Ads: (regex, replacement builder, issue, reason, extra alternatives).
AD_RULES = [
    (
        r"\bwith\s+(?:no|zero)\s+risk(?:\s+at\s+all)?",
        lambda m: "with less risk",
        "Risk-free claim",
        "Ads must not promise that there is no risk.",
        ["with reduced risk", "with confidence"],
    ),
    (
        r"\brisk[- ]free\b",
        lambda m: "low-risk",
        "Risk-free claim",
        "Ads must not promise that there is no risk.",
        ["lower-risk", "designed to reduce risk"],
    ),
    (
        r"\b(?:faster|better|cheaper|easier|stronger|smarter)\s+than\s+"
        r"(?:ever(?:\s+before)?|any\w*|others|the\s+rest|competitors)\b",
        lambda m: "with confidence",
        "Unsupported comparison",
        "Comparisons need evidence, so Ads should not make them.",
        ["more efficiently", "with ease"],
    ),
]


def _rule_based(text, claims_policy, content_type="Blog"):
    """Run the built-in patterns. Earlier rules win when two matches overlap."""
    rule_text = f"Claims policy: {claims_policy}" if claims_policy else "Claims need supporting evidence"
    rules = RULES + (AD_RULES if content_type == "Ad" else [])
    taken = []  # spans already used
    findings = []

    for rule in rules:
        pattern, build, issue, reason = rule[:4]
        extras = rule[4] if len(rule) > 4 else []
        for m in re.finditer(pattern, text, flags=re.IGNORECASE):
            start, end = m.start(), m.end()
            if any(start < t_end and end > t_start for t_start, t_end in taken):
                continue
            taken.append((start, end))

            suggestion = capitalise_at_sentence_start(text, start, build(m))
            finding = make_finding("claim", text[start:end], start, end, issue, reason, rule_text, suggestion)
            findings.append(add_alternatives(finding, extras))
    return findings


def _ai_based(text, claims_policy, content_type="Blog", channel_rules=None):
    """Ask Gemini for extra claims. Returns [] if the AI is unavailable or answers badly."""
    if not llm_client.is_configured():
        return []
    try:
        items = llm_client.ask_for_findings(
            "claims_prompt.txt",
            claims_policy=claims_policy,
            channel=content_type,
            channel_guidance=channel_guidance(content_type, channel_rules),
            text=text,
        )
    except llm_client.LLMError as error:
        print(f"[claim_checker] AI skipped: {error}")
        return []

    findings = []
    for item in items:
        quote = str(item.get("text", "")).strip()
        start = text.find(quote) if quote else -1
        if start == -1:
            continue  # the AI quoted something that is not in the content; ignore it
        finding = make_finding(
            "claim",
            quote,
            start,
            start + len(quote),
            str(item.get("issue") or "Claim needs evidence"),
            str(item.get("reason") or ""),
            str(item.get("rule") or claims_policy or "Claims need supporting evidence"),
            str(item.get("suggestion") or ""),
            source="ai",
        )
        extras = item.get("alternatives")
        findings.append(add_alternatives(finding, extras if isinstance(extras, list) else []))
    return findings


def check_claims(text, claims_policy="", content_type="Blog", channel_rules=None):
    """Returns claim findings. Overlaps between the rules and the AI are removed by review_service."""
    return _rule_based(text, claims_policy, content_type) + _ai_based(text, claims_policy, content_type, channel_rules)