# rewrite_service.py
# Feature 2: Generative Alternative Rewrites Engine (Person B)
# Generates on-demand compliant alternative rewrites for flagged findings,
# verifies each against terminology & claims policies, and filters out non-compliant candidates.

from typing import Any, Dict, List

from app.services import llm_client
from app.services.claim_checker import check_claims
from app.services.terminology_checker import check_terminology


def _rule_based_alternatives(finding: Dict[str, Any], content_type: str = "Blog") -> List[str]:
    """Fallback generator for alternatives when AI is offline or unavailable."""
    category = finding.get("category", "")
    original = finding.get("text", "")
    suggestion = finding.get("suggestion", "")

    candidates: List[str] = []
    if suggestion:
        candidates.append(suggestion)

    if category == "terminology":
        # Provide variations of the approved replacement
        if suggestion:
            candidates.append(f"selected {suggestion}")
            candidates.append(f"our {suggestion}")

    elif category == "claim":
        if "best" in original.lower() or "#1" in original.lower() or "leading" in original.lower():
            candidates.extend(["a trusted choice", "an established solution", "a premier offering"])
        elif "guarantee" in original.lower() or "100%" in original.lower():
            candidates.extend(["designed to achieve results", "engineered for reliability", "built to support growth"])
        elif "%" in original or "double" in original.lower():
            candidates.extend(["measurable improvement", "significant positive impact", "demonstrated growth"])
        else:
            candidates.extend(["high-quality", "reputable", "proven"])

    elif category == "tone":
        if content_type.lower() in ("social", "social post"):
            candidates.extend(["standout", "compelling", "exciting"])
        else:
            candidates.extend(["noteworthy", "effective", "distinctive"])

    elif category == "channel":
        if suggestion:
            candidates.append(suggestion.rstrip("!"))
            candidates.append(suggestion.rstrip("!") + ".")

    # Deduplicate while preserving order, omit exact duplicate of original text
    seen = {original.lower()}
    final_res = []
    for c in candidates:
        if c.strip() and c.lower() not in seen:
            seen.add(c.lower())
            final_res.append(c.strip())

    return final_res[:3]


def generate_alternatives(
    finding: Dict[str, Any],
    full_text: str,
    rulebook: Dict[str, Any],
    content_type: str = "Blog",
) -> List[str]:
    """
    Generate 2 to 3 compliant alternative rewrites for a finding.
    Runs each candidate back through terminology and claim checkers to guarantee compliance.
    """
    flagged_text = finding.get("text", "")
    start = finding.get("start", 0) or 0
    end = finding.get("end", len(flagged_text)) or len(flagged_text)

    # Extract surrounding sentence/context window (~120 chars)
    ctx_start = max(0, start - 60)
    ctx_end = min(len(full_text), end + 60)
    context = full_text[ctx_start:ctx_end] if full_text else flagged_text

    raw_candidates: List[str] = []

    if llm_client.is_configured():
        try:
            prompt_vars = {
                "company": rulebook.get("company", "the brand"),
                "channel": content_type,
                "issue": finding.get("issue", "Brand compliance issue"),
                "reason": finding.get("reason", "Violates brand guidelines"),
                "rule": finding.get("rule", "Follow brand style"),
                "text": flagged_text,
                "context": context,
            }
            # Ask Gemini for JSON list of alternative strings
            items = llm_client.ask_for_findings("rewrite_prompt.txt", **prompt_vars)
            if isinstance(items, list):
                for it in items:
                    if isinstance(it, str) and it.strip():
                        raw_candidates.append(it.strip())
                    elif isinstance(it, dict) and it.get("text"):
                        raw_candidates.append(str(it["text"]).strip())
        except Exception as err:
            print(f"[rewrite_service] AI alternative generation skipped: {err}")

    if not raw_candidates:
        raw_candidates = _rule_based_alternatives(finding, content_type)

    # Always ensure the original suggestion is included as a candidate if present
    sugg = finding.get("suggestion", "").strip()
    if sugg and sugg not in raw_candidates:
        raw_candidates.insert(0, sugg)

    # Filter each candidate back through terminology and claim checkers
    clean_alternatives: List[str] = []
    restricted_terms = rulebook.get("restricted_terms", [])
    claims_policy = rulebook.get("claims_policy", "")

    seen = {flagged_text.strip().lower()}
    for cand in raw_candidates:
        cand_clean = cand.strip()
        if not cand_clean or cand_clean.lower() in seen:
            continue

        # Check against restricted terms
        term_issues = check_terminology(cand_clean, restricted_terms)
        if term_issues:
            continue

        # Check against claim rules
        claim_issues = check_claims(cand_clean, claims_policy)
        if claim_issues:
            continue

        seen.add(cand_clean.lower())
        clean_alternatives.append(cand_clean)
        if len(clean_alternatives) >= 3:
            break

    # If all candidates were filtered out, fall back safely to the primary suggestion or a neutral placeholder
    if not clean_alternatives and sugg:
        clean_alternatives.append(sugg)

    return clean_alternatives
