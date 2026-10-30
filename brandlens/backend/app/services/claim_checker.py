# claim_checker.py
# Flags promotional claims that need evidence: rankings ("#1", "best"), guaranteed results,
# statistics and "will double your sales" promises.
# Built-in rules always run (so it works without AI). Stricter rules apply for Ads.

import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.services import llm_client
from app.services.suggestion_engine import (
    capitalise_at_sentence_start,
    make_finding,
    plural,
)

# Words that must not be swallowed as part of a noun ("best IN the world", "best FOR you").
STOP = r"(?:in|for|of|and|that|is|on|to|way|with)\b"

# Each rule: (regex, builder that makes the replacement text from the match, issue title, why it needs evidence, alternatives).
BASE_RULES: List[Tuple[str, Callable[[Any], str], str, str, List[str]]] = [
    (
        rf"\b(?:the\s+)?(?:best|leading)\s+(?!{STOP})([\w-]+(?:\s(?!{STOP})[\w-]+)?)"
        r"(?:\s+in\s+(?:the\s+)?(?:industry|market|world|business))?",
        lambda m: f"a trusted {m.group(1)}",
        "Unsupported ranking claim",
        "Superlatives such as best, leading or top need independent evidence.",
        ["an established option", "a respected choice", "a reliable provider"],
    ),
    (
        r"\bthe\s+most\s+(\w+)\s+([\w-]+(?:\s[\w-]+)?)\s+ever\s+(?:built|made|created)",
        lambda m: f"a {m.group(1)} {m.group(2)}",
        "Unsupported superlative",
        '"Most ... ever" cannot be proven without verified empirical benchmarks.',
        ["a powerful option", "an advanced product", "a modern solution"],
    ),
    (
        r"\bthe\s+#\s*1\s+(choice|solution|platform|provider)\b",
        lambda m: f"a trusted {m.group(1)}",
        "Unsupported ranking claim",
        "A #1 ranking needs a named, verifiable third-party source.",
        ["a preferred choice", "a recognized option", "a widely-used solution"],
    ),
    (
        r"#\s*1(?:\s+in\s+the\s+(?:world|industry|market|business))?|\bnumber[- ]one(?:\s+in\s+the\s+\w+)?",
        lambda m: "a trusted name",
        "Unsupported ranking claim",
        "A #1 ranking needs a named, verifiable third-party source.",
        ["an industry leader", "a recognized authority", "a preferred partner"],
    ),
    (
        r"\b(?:a\s+|an\s+)?\d[\d,]*(?:\.\d+)?%\s+(?:increase|boost|growth|jump|rise|improvement)\s+in\s+([\w-]+)",
        lambda m: f"an increase in {m.group(1)}",
        "Unsourced statistic",
        "Performance numbers must be backed by citations or verified case studies.",
        ["measurable growth in this area", "enhanced performance", "positive trends"],
    ),
    (
        r"\b(?:double|triple|quadruple)s?\s+(revenue|sales|profits?|growth|conversions?)"
        r"(?:\s+for\s+(?:every|all|each)\s+(\w+))?",
        lambda m: f"help {plural(m.group(2)) if m.group(2) else 'businesses'} grow {m.group(1)}",
        "Guaranteed-result claim",
        "Promising specific financial outcomes for everyone cannot be legally guaranteed.",
        ["support positive growth", "help accelerate performance", "contribute to revenue goals"],
    ),
    (
        r"\b(?:are|is|will\s+be)\s+guaranteed\s+to\s+(go\s+up|increase|grow)",
        lambda m: f"may {m.group(1)}",
        "Guaranteed-result claim",
        "Future outcomes cannot be unconditionally guaranteed.",
        ["is designed to support", "is engineered to help", "aims to improve"],
    ),
    (
        r"\b(?:100%\s+)?guaranteed?\s+(results|success|growth|savings)\b",
        lambda m: f"designed to deliver {m.group(1)}",
        "Guaranteed-result claim",
        "Unconditional guarantees expose the organization to legal and regulatory liability.",
        ["focused on measurable progress", "aimed at delivering value", "built to drive performance"],
    ),
    (
        r"\brevolutionary\b|\bgame[- ]chang(?:er|ing)\b",
        lambda m: "innovative",
        "Unsupported superlative",
        "Hype terms like 'revolutionary' lack factual basis without third-party validation.",
        ["forward-thinking", "modern", "high-impact"],
    ),
    (
        r"\bunmatched\b|\bunrivall?ed\b|\bunbeatable\b|\bworld[- ]class\b",
        lambda m: "high-quality",
        "Unsupported superlative",
        "Absolute quality claims require documented comparative evidence.",
        ["premier", "exceptional", "distinguished"],
    ),
    (
        r"\b(?:best|leading)\b(?!\s*,|\s+(?:regards|wishes))",
        lambda m: "trusted",
        "Unsupported ranking claim",
        "Superlatives such as best or leading need independent evidence.",
        ["dedicated", "established", "specialized"],
    ),
]

# Additional stricter rules applied for Advertising and Landing Pages
AD_STRICT_RULES: List[Tuple[str, Callable[[Any], str], str, str, List[str]]] = [
    (
        r"\b(?:100%\s+)?(?:risk[- ]free|no\s+risk)\b",
        lambda m: "backed by our customer satisfaction policy",
        "Misleading risk-free claim (Ad Compliance)",
        "Advertising standards prohibit unqualified 'risk-free' claims without full terms disclosed.",
        ["satisfaction-focused", "transparent trial terms", "straightforward cancellation"],
    ),
    (
        r"\b(?:instant|overnight)\s+(?:results|success|growth|impact)\b",
        lambda m: "rapid implementation",
        "Unrealistic outcome promise (Ad Compliance)",
        "Advertising standards prohibit promising instant or overnight business transformation.",
        ["fast onboarding", "efficient rollout", "accelerated adoption"],
    ),
    (
        r"\bfree\s+forever\b",
        lambda m: "free starter tier",
        "Unqualified 'free' claim (Ad Compliance)",
        "Advertising standards require clear qualification for free product offers.",
        ["complimentary tier", "free plan available", "starter plan at no cost"],
    ),
    (
        r"\b(?:lowest|cheapest)\s+(?:prices?|rates?|costs?)\b",
        lambda m: "competitive pricing",
        "Unverified price guarantee (Ad Compliance)",
        "Comparative price claims ('lowest/cheapest') require continuous market price monitoring.",
        ["transparent pricing", "cost-effective plans", "value-driven rates"],
    ),
]


def _rule_based(
    text: str,
    claims_policy: str,
    content_type: str = "Blog",
    channel_rules: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    rule_text = f"Claims policy: {claims_policy}" if claims_policy else "Claims need supporting evidence"
    taken = []
    findings = []

    # Compile rules list: include stricter rules for Ad channels
    active_rules = list(BASE_RULES)
    if content_type.lower() in ("ad", "landing page"):
        active_rules = AD_STRICT_RULES + active_rules

    for pattern, build, issue, reason, alts in active_rules:
        for m in re.finditer(pattern, text, flags=re.IGNORECASE):
            start, end = m.start(), m.end()
            if any(start < t_end and end > t_start for t_start, t_end in taken):
                continue
            taken.append((start, end))

            suggestion = capitalise_at_sentence_start(text, start, build(m))
            findings.append(
                make_finding(
                    category="claim",
                    text=text[start:end],
                    start=start,
                    end=end,
                    issue=issue,
                    reason=reason,
                    rule=rule_text,
                    suggestion=suggestion,
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
    if lower_q.startswith("the most "):
        return quote[9:].strip()
    elif lower_q.startswith("most "):
        return quote[5:].strip()
    elif lower_q.startswith("the #1 ") or lower_q.startswith("#1 "):
        return "a trusted"
    elif "cure" in lower_q or "fatigue" in lower_q:
        return "are crafted for an afternoon boost" if lower_q.startswith("are ") else "crafted for an afternoon boost"
    elif lower_q == "cheap":
        return "affordable"

    return s


def _ai_based(
    text: str,
    claims_policy: str,
    content_type: str = "Blog",
    channel_rules: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    if not llm_client.is_configured():
        return []

    channel_guidance = ""
    if content_type.lower() in ("ad", "landing page"):
        channel_guidance = "Strict Advertising Compliance: Flag all unqualified superlatives, ROI guarantees, and unproven claims."
    elif content_type.lower() in ("press release",):
        channel_guidance = "Strict Media Compliance: All statistics and performance metrics must reference verifiable sources."

    try:
        items = llm_client.ask_for_findings(
            "claims_prompt.txt",
            claims_policy=claims_policy or "Factual claims and superlatives require evidence",
            channel=content_type,
            channel_guidance=channel_guidance,
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
            continue

        raw_alts = item.get("alternatives")
        alts = [str(a).strip() for a in raw_alts if str(a).strip()] if isinstance(raw_alts, list) else []

        clean_sugg = _clean_replacement(quote, str(item.get("suggestion") or ""), alts)

        findings.append(
            make_finding(
                category="claim",
                text=quote,
                start=start,
                end=start + len(quote),
                issue=str(item.get("issue") or "Claim needs evidence"),
                reason=str(item.get("reason") or ""),
                rule=str(item.get("rule") or claims_policy or "Claims need supporting evidence"),
                suggestion=clean_sugg,
                alternatives=alts,
                source="ai",
            )
        )
    return findings


def check_claims(
    text: str,
    claims_policy: str = "",
    content_type: str = "Blog",
    channel_rules: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Returns claim findings with stricter checks applied to advertising channels."""
    return _rule_based(text, claims_policy, content_type, channel_rules) + _ai_based(
        text, claims_policy, content_type, channel_rules
    )
