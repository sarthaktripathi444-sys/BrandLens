# suggestion_engine.py
# Small helpers shared by all checkers: build a finding, keep capital letters right,
# remove overlapping findings, and apply the accepted fixes to the text.

import re

# When two findings cover the same words, the one with the LOWER number wins.
# (Facts and claims are more serious than a word swap, and a word swap is more exact than a tone note.)
PRIORITY = {"fact": 0, "claim": 1, "terminology": 2, "tone": 3}


def make_finding(category, text, start, end, issue, reason, rule, suggestion="", source="rule"):
    """Build one finding as a plain dictionary (the id and status are added later by review_service)."""
    return {
        "category": category,
        "text": text,
        "start": start,
        "end": end,
        "issue": issue,
        "reason": reason,
        "rule": rule,
        "suggestion": suggestion,
        "source": source,
    }


def match_case(original, replacement):
    """Copy the capital-letter style of the original word onto the replacement.
    'Users' -> 'Customers',  'USERS' -> 'CUSTOMERS',  'users' -> 'customers'."""
    if len(original) > 1 and original.isupper():
        return replacement.upper()
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def capitalise_at_sentence_start(text, start, replacement):
    """If the replacement begins a sentence, make its first letter a capital."""
    before = text[:start].rstrip(" \t")
    if not before or before[-1] in ".!?\n":
        return replacement[:1].upper() + replacement[1:]
    return replacement


def plural(word):
    """Very small English pluralizer: customer -> customers, company -> companies, box -> boxes."""
    if re.search(r"[^aeiou]y$", word):
        return word[:-1] + "ies"
    if re.search(r"(s|x|z|ch|sh)$", word):
        return word + "es"
    return word + "s"


def remove_overlaps(findings):
    """Keep at most one finding for any stretch of text, preferring higher-priority categories.
    Findings without a position are always kept. The result is sorted by position in the text."""
    positioned = [f for f in findings if isinstance(f.get("start"), int) and isinstance(f.get("end"), int)]
    unpositioned = [f for f in findings if f not in positioned]

    kept = []
    for f in sorted(positioned, key=lambda f: (PRIORITY.get(f["category"], 9), f["start"])):
        if all(f["end"] <= k["start"] or f["start"] >= k["end"] for k in kept):
            kept.append(f)

    kept.sort(key=lambda f: f["start"])
    return kept + unpositioned


def apply_accepted(text, findings):
    """Return the text with every ACCEPTED suggestion swapped in.
    Works from the end of the text backwards so earlier positions stay correct."""
    result = text
    usable = [
        f for f in findings
        if f.get("status") == "accepted"
        and (f.get("replacement") or f.get("suggestion"))
        and isinstance(f.get("start"), int)
        and isinstance(f.get("end"), int)
    ]
    for f in sorted(usable, key=lambda f: f["start"], reverse=True):
                wording = f.get("replacement") or f["suggestion"]
                result = result[: f["start"]] + wording + result[f["end"]:]
    return result
