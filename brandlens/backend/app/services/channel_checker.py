# channel_checker.py
# Format rules that depend on where the content will be published (Email, Social Post, Ad...).
# The rules come from the rule book's "channel_rules", keyed by content type. No AI is used here.

import re

from app.services.suggestion_engine import make_finding


def _last_line(text):
    stripped = text.rstrip()
    return stripped.rfind("\n") + 1, len(stripped)


def check_channel(text, content_type, channel_rules):
    rule = (channel_rules or {}).get(content_type)
    if not isinstance(rule, dict):
        return []

    rule_name = f"Channel rule: {content_type}"
    findings = []

    # Email subject length ("Subject: ..." on the first line).
    max_subject = rule.get("max_subject_chars")
    match = re.match(r"\s*subject\s*:\s*(.+)", text, flags=re.IGNORECASE)
    if max_subject and match:
        subject = match.group(1).rstrip()
        if len(subject) > max_subject:
            start = match.start(1)
            findings.append(make_finding(
                "tone", subject, start, start + len(subject),
                f"Subject line too long ({len(subject)}/{max_subject} characters)",
                f"{content_type} subject lines should be at most {max_subject} characters.",
                rule_name, subject,
            ))

    # Total length.
    max_chars = rule.get("max_chars")
    end_of_text = len(text.rstrip())
    if max_chars and end_of_text > max_chars:
        findings.append(make_finding(
            "tone", text[max_chars:end_of_text], max_chars, end_of_text,
            f"Too long for {content_type} ({end_of_text}/{max_chars} characters)",
            f"{content_type} content should be at most {max_chars} characters. Shorten it by hand.",
            rule_name, text[max_chars:end_of_text],
        ))

    # Exclamation marks.
    if rule.get("allow_exclamation") is False:
        for found in re.finditer(r"!+", text):
            findings.append(make_finding(
                "tone", found.group(0), found.start(), found.end(),
                f"Exclamation marks not allowed in {content_type}",
                f"The {content_type} rules do not allow exclamation marks.",
                rule_name, ".",
            ))

    # Hashtags.
    max_tags = rule.get("max_hashtags")
    if max_tags is not None:
        for found in list(re.finditer(r"#\w+", text))[max_tags:]:
            findings.append(make_finding(
                "tone", found.group(0), found.start(), found.end(),
                f"Too many hashtags (limit {max_tags})",
                f"{content_type} content can have at most {max_tags} hashtags. Remove this one.",
                rule_name, found.group(0),
            ))

    # Required disclaimer.
    disclaimer = (rule.get("required_disclaimer") or "").strip()
    if disclaimer and disclaimer.lower() not in text.lower():
        start, end = _last_line(text)
        last_line = text[start:end]
        if last_line.strip():
            findings.append(make_finding(
                "tone", last_line, start, end,
                "Missing required disclaimer",
                f"{content_type} content must include: {disclaimer}",
                rule_name, f"{last_line} {disclaimer}",
            ))

    return findings