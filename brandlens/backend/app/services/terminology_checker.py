# terminology_checker.py
# Finds restricted words from the rule book (e.g. "user") and suggests the approved word ("customer").
# Plain Python, no AI. Matches whole words only, ignores capital letters, and handles plurals.

import re

from app.services.suggestion_engine import (
    capitalise_at_sentence_start,
    make_finding,
    match_case,
    plural,
)


def check_terminology(text, restricted_terms):
    """restricted_terms is a list of {"term", "use", "reason"}. Returns a list of findings."""
    findings = []

    for rule in restricted_terms:
        term = (rule.get("term") or "").strip()
        use = (rule.get("use") or "").strip()
        if not term:
            continue

        # Whole word, optionally followed by a plural ending: user / users, company / companies not needed.
        pattern = re.compile(rf"(?<!\w){re.escape(term)}(s|es)?(?!\w)", flags=re.IGNORECASE)

        for m in pattern.finditer(text):
            start, end = m.start(), m.end()
            is_plural = bool(m.group(1)) and not term.lower().endswith("s")

            replacement = plural_last_word(use) if is_plural else use

            # Avoid "designed to to": if the replacement already ends with the next word, swallow that word too.
            if replacement:
                nxt = re.match(r"\s+(\w+)", text[end:])
                if nxt and replacement.split()[-1].lower() == nxt.group(1).lower():
                    end += nxt.end()

            original = text[start:end]
            suggestion = match_case(original, replacement) if replacement else ""
            suggestion = capitalise_at_sentence_start(text, start, suggestion) if suggestion else ""

            findings.append(
                make_finding(
                    category="terminology",
                    text=original,
                    start=start,
                    end=end,
                    issue=f'Avoid the word "{term}"',
                    reason=rule.get("reason") or f'The brand does not use "{term}".',
                    rule=f'Use "{use}" instead of "{term}"' if use else f'Do not use "{term}"',
                    suggestion=suggestion,
                )
            )

    return findings


def plural_last_word(phrase):
    """'customer' -> 'customers'; 'business partner' -> 'business partners'."""
    words = phrase.split()
    if not words:
        return phrase
    words[-1] = plural(words[-1])
    return " ".join(words)
