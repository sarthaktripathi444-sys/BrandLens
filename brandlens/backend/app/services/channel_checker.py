# channel_checker.py
# Feature 2: Channel-Aware Format & Compliance Checker (Person B)
# Evaluates format constraints tailored to specific media channels
# (Social Post, Email, Ad, Press Release, Blog).

import re
from typing import Any, Dict, List, Optional

from app.services.suggestion_engine import make_finding


def _find_channel_rule(channel_rules: Dict[str, Any], content_type: str) -> Optional[Dict[str, Any]]:
    """Look up channel rules with fuzzy matching (e.g. 'Social' matches 'Social Post')."""
    if not channel_rules:
        return None

    ct_lower = content_type.strip().lower()
    for key, rule in channel_rules.items():
        k_lower = key.strip().lower()
        if k_lower == ct_lower:
            return rule.dict() if hasattr(rule, "dict") else dict(rule)
        if ct_lower in k_lower or k_lower in ct_lower:
            return rule.dict() if hasattr(rule, "dict") else dict(rule)

    return None


def check_channel(
    text: str,
    channel_rules: Optional[Dict[str, Any]] = None,
    content_type: str = "Blog",
) -> List[Dict[str, Any]]:
    """
    Run format and constraint checks for the specified content channel.
    Checks character lengths, subject lines, hashtag limits, exclamation rules,
    and mandatory legal/regulatory disclaimers.
    """
    if not text:
        return []

    channel_rules = channel_rules or {}
    rule = _find_channel_rule(channel_rules, content_type) or {}
    findings: List[Dict[str, Any]] = []

    # 1. Check max characters
    max_chars = rule.get("max_chars")
    # Sensible defaults if not specified: Social Post default max chars 280/500
    if max_chars is None and content_type.lower() in ("social", "social post"):
        max_chars = 500

    if max_chars and len(text) > max_chars:
        excess = len(text) - max_chars
        findings.append(
            make_finding(
                category="channel",
                text=text[max_chars:],
                start=max_chars,
                end=len(text),
                issue=f"{content_type} character limit exceeded",
                reason=f"Content is {len(text)} characters, exceeding the {max_chars} character limit for {content_type} by {excess} characters.",
                rule=f"{content_type} max length: {max_chars} characters",
                suggestion=text[:max_chars],
                source="rule",
            )
        )

    # 2. Check email subject line length (for Email channel)
    max_subj = rule.get("max_subject_chars")
    if max_subj is None and content_type.lower() == "email":
        max_subj = 60  # Default best-practice email subject limit

    if max_subj and content_type.lower() == "email":
        # Look for explicit Subject line or evaluate first line
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if lines:
            first_line = lines[0]
            subj_match = re.match(r"^Subject:\s*(.*)$", first_line, re.IGNORECASE)
            subject_text = subj_match.group(1).strip() if subj_match else first_line

            if len(subject_text) > max_subj:
                # Find span of subject in text
                subj_start = text.find(subject_text)
                subj_end = subj_start + len(subject_text) if subj_start != -1 else len(first_line)
                if subj_start == -1:
                    subj_start = 0

                findings.append(
                    make_finding(
                        category="channel",
                        text=subject_text,
                        start=subj_start,
                        end=subj_end,
                        issue=f"Email subject exceeds recommended length",
                        reason=f"Subject line is {len(subject_text)} characters. Email subjects should stay under {max_subj} characters to avoid being clipped in mobile inboxes.",
                        rule=f"Email max subject length: {max_subj} characters",
                        suggestion=subject_text[:max_subj].rsplit(" ", 1)[0] if " " in subject_text[:max_subj] else subject_text[:max_subj],
                        source="rule",
                    )
                )

    # 3. Check exclamation mark allowance
    allow_exclamation = rule.get("allow_exclamation", True)
    # Stricter default: Press Releases and Ads should discourage exclamation marks
    if content_type.lower() in ("press release", "ad"):
        allow_exclamation = False

    if not allow_exclamation:
        for m in re.finditer(r"!+", text):
            findings.append(
                make_finding(
                    category="channel",
                    text=m.group(0),
                    start=m.start(),
                    end=m.end(),
                    issue=f"Exclamation marks disallowed in {content_type}",
                    reason=f"Exclamation marks compromise the professional tone required for {content_type} materials.",
                    rule=f"{content_type} style: no exclamation marks",
                    suggestion=".",
                    source="rule",
                )
            )

    # 4. Check hashtag limits (for Social channels)
    max_hashtags = rule.get("max_hashtags")
    if max_hashtags is None and content_type.lower() in ("social", "social post"):
        max_hashtags = 5  # Default social best practice

    if max_hashtags is not None:
        hashtags = list(re.finditer(r"#\w+", text))
        if len(hashtags) > max_hashtags:
            excess_tags = hashtags[max_hashtags:]
            first_excess = excess_tags[0]
            last_excess = excess_tags[-1]
            findings.append(
                make_finding(
                    category="channel",
                    text=text[first_excess.start():last_excess.end()],
                    start=first_excess.start(),
                    end=last_excess.end(),
                    issue=f"Hashtag limit exceeded for {content_type}",
                    reason=f"Found {len(hashtags)} hashtags. {content_type} allows a maximum of {max_hashtags} hashtags to avoid triggering spam filters.",
                    rule=f"{content_type} hashtag limit: {max_hashtags}",
                    suggestion="",
                    source="rule",
                )
            )

    # 5. Check required disclaimers (e.g. for Ads, Financial, or Medical claims)
    required_disclaimer = rule.get("required_disclaimer", "").strip()
    if required_disclaimer:
        if required_disclaimer.lower() not in text.lower():
            findings.append(
                make_finding(
                    category="channel",
                    text="(Missing disclaimer)",
                    start=len(text),
                    end=len(text),
                    issue=f"Missing mandatory disclaimer for {content_type}",
                    reason=f"{content_type} content is legally required to include: \"{required_disclaimer}\"",
                    rule=f"Mandatory disclaimer: \"{required_disclaimer}\"",
                    suggestion=f"\n\n{required_disclaimer}",
                    alternatives=[f"\n\n* {required_disclaimer}", f"\n\n[{required_disclaimer}]"],
                    source="rule",
                )
            )

    return findings
