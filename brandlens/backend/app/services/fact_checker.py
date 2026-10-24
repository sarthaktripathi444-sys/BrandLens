# fact_checker.py
# Compares numbers in the content with the true facts in the rule book
# (e.g. rule book says 14,000 customers, content says "50,000 users").
# Plain Python, no AI.

import re

from app.services.suggestion_engine import make_finding

# A number such as 50000, 50,000 or 2.5 ; optionally followed by k / thousand / million.
NUMBER = r"\d[\d,]*(?:\.\d+)?"
MULTIPLIER = r"(?:\s*(?:k|K|thousand|million|m|M)\b)?"

# Words in front of a number that turn it into a range ("over 10,000" is true if the real value is higher).
LOWER_BOUND = r"(?:over|more than|at least|above|exceeding)"
UPPER_BOUND = r"(?:under|less than|fewer than|up to|below)"
HEDGE = rf"(?P<hedge>(?:{LOWER_BOUND}|{UPPER_BOUND})\s+)?"


def to_number(raw, multiplier):
    """'50,000' -> 50000.0 ; '2.5' + 'million' -> 2500000.0. Returns None if it is not a number."""
    try:
        value = float(raw.replace(",", ""))
    except ValueError:
        return None
    word = (multiplier or "").strip().lower()
    if word in ("k", "thousand"):
        value *= 1_000
    elif word in ("m", "million"):
        value *= 1_000_000
    return value


def pretty(value, is_year):
    """Show 14000.0 as '14,000' and 2019.0 as '2019'."""
    if float(value).is_integer():
        value = int(value)
        return str(value) if is_year else f"{value:,}"
    return str(value)


def is_year_fact(value):
    """A fact like founded=2019 is a year; those are matched differently from counts."""
    try:
        return 1800 <= int(float(value)) <= 2100
    except (TypeError, ValueError):
        return False


def check_facts(text, facts):
    """facts is a list of {"label", "aliases", "value"}. Returns a list of findings."""
    findings = []
    seen = set()

    for fact in facts:
        label = fact.get("label", "fact")
        try:
            true_value = float(str(fact.get("value")).replace(",", ""))
        except ValueError:
            continue  # text facts (e.g. a CEO name) cannot be compared as numbers

        year_fact = is_year_fact(true_value)
        aliases = [a for a in (fact.get("aliases") or []) if a] or [label]
        alias_pattern = "|".join(re.escape(a) for a in sorted(aliases, key=len, reverse=True))

        if year_fact:
            # "founded in 2016", "since 2015": the year comes AFTER the keyword.
            pattern = (
                rf"\b(?P<alias>{alias_pattern})\b(?:\s+[\w']+){{0,3}}?\s+(?P<num>(?:18|19|20)\d{{2}})\b"
            )
        else:
            # "50,000 users", "over 20,000 clients": the number comes BEFORE the keyword.
            pattern = (
                rf"{HEDGE}(?P<num>{NUMBER})(?P<mult>{MULTIPLIER})(?!\s*%)"
                rf"\s+(?:[\w-]+\s+){{0,2}}?(?P<alias>{alias_pattern})\b"
            )

        for m in re.finditer(pattern, text, flags=re.IGNORECASE):
            found = to_number(m.group("num"), m.groupdict().get("mult"))
            if found is None:
                continue

            hedge = (m.groupdict().get("hedge") or "").strip().lower()
            if re.fullmatch(LOWER_BOUND, hedge):
                correct = found <= true_value      # "over 10,000" is fine if the truth is 14,000
            elif re.fullmatch(UPPER_BOUND, hedge):
                correct = found >= true_value
            else:
                correct = abs(found - true_value) < 1e-9
            if correct:
                continue

            # Highlight the hedge word + number (not the keyword, so it never clashes with a word swap).
            start = m.start("hedge") if hedge and m.group("hedge") else m.start("num")
            end = m.end("num") if year_fact else m.end("mult")
            if (start, end) in seen:
                continue
            seen.add((start, end))

            correct_text = pretty(true_value, year_fact)
            findings.append(
                make_finding(
                    category="fact",
                    text=text[start:end],
                    start=start,
                    end=end,
                    issue=f"Incorrect {label}",
                    reason=f"The rule book says {label} is {correct_text}, but the content says {text[start:end].strip()}.",
                    rule=f"Fact: {label} = {correct_text}",
                    suggestion=correct_text,
                )
            )

    return findings
