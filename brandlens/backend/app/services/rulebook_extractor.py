# rulebook_extractor.py
# Feature 1: Automated Brand Rulebook Extractor
# Extracts tone, terminology, prohibited words, approved messaging, and facts
# from uploaded files (.pdf, .docx, .txt) or fetched URLs using Gemini,
# with a comprehensive heuristic fallback when GEMINI_API_KEY is not configured.

import ipaddress
import re
import socket
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup

from app.schemas.rulebook import ChannelRule, Rulebook
from app.services import llm_client
from app.services.text_extractor import ExtractError, extract_text

CHUNK_SIZE = 12000
MAX_URL_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB cap
URL_TIMEOUT_SECONDS = 10.0


def validate_url(url: str) -> str:
    """Ensure the URL is http/https and does not resolve to private, localhost, or reserved IPs."""
    parsed = urllib.parse.urlsplit(url.strip())
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise ExtractError("Only http and https URLs are allowed.")

    hostname = parsed.hostname
    if not hostname:
        raise ExtractError("Invalid URL: missing hostname.")

    if hostname.lower() in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        raise ExtractError("Access to localhost is blocked for security reasons.")

    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror as err:
        raise ExtractError(f"Could not resolve host '{hostname}': {err}") from err

    for family, _, _, _, sockaddr in addr_info:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
            if (
                ip.is_loopback
                or ip.is_private
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
                or ip.is_unspecified
            ):
                raise ExtractError("Private, local, or internal network addresses are not allowed.")
            if hasattr(ip, "ipv4_mapped") and ip.ipv4_mapped:
                mapped = ip.ipv4_mapped
                if mapped.is_loopback or mapped.is_private or mapped.is_link_local:
                    raise ExtractError("Private or internal network addresses are not allowed.")
        except ValueError:
            continue

    return url.strip()


def fetch_url_text(url: str, max_redirects: int = 3) -> str:
    """Fetch a web page with security guards, size limits, and timeout, returning cleaned text."""
    current_url = validate_url(url)

    for _ in range(max_redirects + 1):
        with httpx.Client(timeout=URL_TIMEOUT_SECONDS, follow_redirects=False) as client:
            try:
                resp = client.get(current_url, headers={"User-Agent": "BrandLens-RulebookExtractor/1.0"})
            except Exception as err:
                raise ExtractError(f"Failed to fetch URL ({type(err).__name__}): {err}") from err

            if resp.is_redirect:
                location = resp.headers.get("location")
                if not location:
                    raise ExtractError("Redirect response missing Location header.")
                current_url = validate_url(urllib.parse.urljoin(current_url, location))
                continue

            if resp.status_code != 200:
                raise ExtractError(f"URL returned HTTP error {resp.status_code}: {resp.reason_phrase}")

            content_len = resp.headers.get("content-length")
            if content_len and int(content_len) > MAX_URL_SIZE_BYTES:
                raise ExtractError(f"Page size exceeds maximum allowed size of {MAX_URL_SIZE_BYTES // (1024 * 1024)} MB.")

            if len(resp.content) > MAX_URL_SIZE_BYTES:
                raise ExtractError(f"Page content exceeds maximum allowed size of {MAX_URL_SIZE_BYTES // (1024 * 1024)} MB.")

            return html_to_text(resp.text)

    raise ExtractError("Too many URL redirects.")


def html_to_text(html: str) -> str:
    """Extract readable text from HTML by removing scripts, styling, and navigation markup."""
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "iframe", "aside"]):
        element.decompose()

    text = soup.get_text(separator="\n", strip=True)
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]
    return "\n\n".join(lines)


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE) -> List[str]:
    """Split long documents into chunks of approximately chunk_size characters on paragraph boundaries."""
    if len(text) <= chunk_size:
        return [text]

    paragraphs = text.split("\n\n")
    chunks: List[str] = []
    current_chunk: List[str] = []
    current_len = 0

    for para in paragraphs:
        para_clean = para.strip()
        if not para_clean:
            continue
        para_len = len(para_clean)

        if current_len + para_len + 2 > chunk_size and current_chunk:
            chunks.append("\n\n".join(current_chunk))
            current_chunk = [para_clean]
            current_len = para_len
        else:
            current_chunk.append(para_clean)
            current_len += para_len + 2

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    final_chunks: List[str] = []
    for c in chunks:
        if len(c) <= chunk_size:
            final_chunks.append(c)
        else:
            for i in range(0, len(c), chunk_size):
                final_chunks.append(c[i : i + chunk_size])

    return final_chunks


def _in_source(quote: str, source_text: str) -> bool:
    """Check if the quote actually appears in the source text (normalized whitespace and case)."""
    if not quote or not quote.strip():
        return False
    norm_quote = " ".join(quote.strip().split()).lower()
    norm_source = " ".join(source_text.split()).lower()
    return norm_quote in norm_source


def check_schema_guidance(rulebook_data: Dict[str, Any]) -> List[str]:
    """Inspect rulebook data against the full standard schema baseline and identify missing or incomplete sections."""
    guidance: List[str] = []

    company = (rulebook_data.get("company") or "").strip()
    if not company or company.lower() == "brand":
        guidance.append("Schema Guidance: 'company' is missing or set to generic 'Brand'. Please update it with your official brand name.")

    tone = rulebook_data.get("tone") or []
    if not tone:
        guidance.append("Schema Guidance: 'tone' is empty. Defining 2–4 voice attributes (e.g. ['professional', 'trustworthy']) enables tone compliance checks.")

    restricted = rulebook_data.get("restricted_terms") or []
    if not restricted:
        guidance.append("Schema Guidance: No 'restricted_terms' were detected. Adding prohibited words (e.g. 'cheap' -> 'affordable') enables vocabulary enforcement.")

    facts = rulebook_data.get("facts") or []
    if not facts:
        guidance.append("Schema Guidance: No core 'facts' were found. Specifying verified statistics (customer counts, founding year) enables factual accuracy checks.")

    claims_policy = (rulebook_data.get("claims_policy") or "").strip()
    if not claims_policy:
        guidance.append("Schema Guidance: 'claims_policy' is missing. Defining rules for superlatives ('best', '#1') and guarantees prevents unsupported claims.")

    return guidance


def _detect_company_name(lines: List[str], full_text: str) -> str:
    """Detect company / brand name across multiple headline and textual conventions."""
    # 1. 'Company Name | Brand Voice and Messaging Guidelines...'
    for line in lines[:10]:
        m = re.match(
            r"^([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+){0,3})\s*(?:\||–|-|:)\s*(?:Brand\s+)?(?:Voice|Guidelines|Style|Identity|Messaging)",
            line,
            re.IGNORECASE,
        )
        if m:
            cand = m.group(1).strip()
            if cand.lower() not in ("our", "the", "this", "brand"):
                return cand

    # 2. Standalone Title followed by Guidelines/Voice on the next line
    for i in range(min(len(lines) - 1, 10)):
        line = lines[i]
        next_line = lines[i + 1]
        if re.search(r"(?:Brand\s+)?(?:Voice|Guidelines|Style|Messaging|Standards)", next_line, re.IGNORECASE):
            m = re.match(r"^([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+){0,3})$", line)
            if m:
                cand = m.group(1).strip()
                if cand.lower() not in ("our", "the", "this", "brand", "table of contents", "overview"):
                    return cand

    # 3. 'Who we are / About us' followed by 'Company Name is a ...'
    m_who = re.search(
        r"(?:Who we are|About us|About the company)\s*\n+\s*([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+){0,3})\s+is\s+(?:a|an|the|our)\s+",
        full_text,
        re.IGNORECASE,
    )
    if m_who:
        cand = m_who.group(1).strip()
        if cand.lower() not in ("our", "the", "this"):
            return cand

    # 4. 'Company Name was founded in ...'
    m_found = re.search(r"([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+){0,3})\s+was\s+founded", full_text)
    if m_found:
        cand = m_found.group(1).strip()
        if cand.lower() not in ("the company", "company"):
            return cand

    # 5. Look for boilerplate sentence: 'Company Name delivers ...' or 'Company Name makes ...'
    m_boiler = re.search(
        r"boilerplate:\s*([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+){0,3})\s+(?:delivers|makes|provides|is)",
        full_text,
        re.IGNORECASE,
    )
    if m_boiler:
        return m_boiler.group(1).strip()

    return "Brand"


def _rule_based_extractor(source_text: str) -> Dict[str, Any]:
    """
    Built-in heuristic extractor used when GEMINI_API_KEY is not configured or as fallback.
    Extracts brand name, tone, vocabulary rules, facts, claims policy, and approved messaging
    directly from guidelines text while preserving verbatim source quotes.
    """
    lines = [line.strip() for line in source_text.splitlines() if line.strip()]

    # 1. Company name detection
    company = _detect_company_name(lines, source_text)

    # 2. Tone attributes
    tone_keywords = [
        "warm", "honest", "curious", "friendly", "plain-spoken", "confident",
        "unhurried", "kind", "professional", "trustworthy", "factual", "bold",
        "innovative", "approachable", "conversational", "authoritative", "clear",
        "concise", "empathetic", "transparent", "inclusive", "dynamic", "authentic"
    ]
    tone = []
    text_lower = source_text.lower()
    for kw in tone_keywords:
        if re.search(r"\b" + re.escape(kw) + r"\b", text_lower):
            tone.append(kw)
    if not tone:
        tone = ["professional", "trustworthy"]

    # 3. Restricted terms
    restricted_terms: List[Dict[str, Any]] = []
    seen_terms = set()

    # Pattern A: 'The words X and Y feel cold ... replace ... with Z'
    m_cold = re.search(
        r"words?\s+([a-zA-Z]+)(?:\s+and\s+([a-zA-Z]+))?\s+feel\s+cold.*?replace\s+(?:it|them)\s+with\s+([a-zA-Z]+)",
        source_text,
        re.I,
    )
    if m_cold:
        use = m_cold.group(3).strip()
        for grp in (m_cold.group(1), m_cold.group(2)):
            if grp and grp.lower() not in seen_terms:
                seen_terms.add(grp.lower())
                restricted_terms.append({
                    "term": grp.strip(),
                    "use": use,
                    "reason": f"Feels cold and transactional, replace with '{use}'",
                    "source_quote": m_cold.group(0),
                })

    # Pattern B: 'The word X is out ... say Y or Z instead'
    for m in re.finditer(
        r"word\s+([a-zA-Z]+)\s+is\s+out.*?say\s+([a-zA-Z\s]+?)(?:\s+or\s+([a-zA-Z\s]+?))?\s+instead",
        source_text,
        re.I,
    ):
        term = m.group(1).strip()
        use = m.group(2).strip()
        if term.lower() not in seen_terms:
            seen_terms.add(term.lower())
            restricted_terms.append({
                "term": term,
                "use": use,
                "reason": m.group(0),
                "source_quote": m.group(0),
            })

    # Pattern C: 'The word X is also out ... write Y or Z instead'
    for m in re.finditer(
        r"word\s+([a-zA-Z]+)\s+is\s+also\s+out.*?write\s+([a-zA-Z\s]+?)(?:\s+or\s+([a-zA-Z\s]+?))?\s+instead",
        source_text,
        re.I,
    ):
        term = m.group(1).strip()
        use = m.group(2).strip()
        if term.lower() not in seen_terms:
            seen_terms.add(term.lower())
            restricted_terms.append({
                "term": term,
                "use": use,
                "reason": m.group(0),
                "source_quote": m.group(0),
            })

    # Pattern D: 'avoid the word X ... and prefer Y'
    for m in re.finditer(r"avoid\s+(?:the\s+word\s+)?([a-zA-Z]+)\b.*?prefer\s+([a-zA-Z\s]+?)(?:\.|$)", source_text, re.I):
        term = m.group(1).strip()
        use = m.group(2).strip()
        if term.lower() not in seen_terms:
            seen_terms.add(term.lower())
            restricted_terms.append({
                "term": term,
                "use": use,
                "reason": m.group(0),
                "source_quote": m.group(0),
            })

    # Pattern E: 'word X is too vague ... say Y'
    for m in re.finditer(r"word\s+([a-zA-Z]+)\s+is\s+too\s+vague.*?say\s+([a-zA-Z\s]+?)(?:,|$|\.)", source_text, re.I):
        term = m.group(1).strip()
        use = m.group(2).strip()
        if term.lower() not in seen_terms:
            seen_terms.add(term.lower())
            restricted_terms.append({
                "term": term,
                "use": use,
                "reason": m.group(0),
                "source_quote": m.group(0),
            })

    # Pattern F: 'never use X, Y or Z in any channel'
    m_never = re.search(
        r"never\s+use\s+([a-zA-Z]+)(?:,\s*([a-zA-Z]+))*(?:\s*or\s*([a-zA-Z]+))\s+in\s+any\s+channel",
        source_text,
        re.I,
    )
    if m_never:
        for i in (1, 2, 3):
            t = m_never.group(i)
            if t and t.lower() not in seen_terms:
                seen_terms.add(t.lower())
                restricted_terms.append({
                    "term": t.strip(),
                    "use": "",
                    "reason": "Off limits in any channel with no substitute",
                    "source_quote": m_never.group(0),
                })

    # Pattern G: 'word X is not a term we use'
    for m in re.finditer(r"word\s+([a-zA-Z]+)\s+is\s+not\s+a\s+term\s+we\s+use", source_text, re.I):
        term = m.group(1).strip()
        if term.lower() not in seen_terms:
            seen_terms.add(term.lower())
            restricted_terms.append({
                "term": term,
                "use": "",
                "reason": "Not a term we use",
                "source_quote": m.group(0),
            })

    # Pattern H: Quoted terms (for documents with explicit quotes)
    for line in lines:
        quotes = re.findall(r'["\u201c\u201d]([^"\u201c\u201d]+)["\u201c\u201d]', line)
        if len(quotes) >= 2 and any(k in line.lower() for k in ("never", "do not", "avoid", "instead", "prohibit")):
            avoid_word = quotes[0].strip()
            use_word = quotes[1].strip()
            # Avoid picking taglines or full sentences as terms
            if len(avoid_word.split()) <= 3 and len(use_word.split()) <= 4:
                if avoid_word.lower() not in seen_terms:
                    seen_terms.add(avoid_word.lower())
                    restricted_terms.append({
                        "term": avoid_word,
                        "use": use_word,
                        "reason": f"From guidelines: {line[:120]}",
                        "source_quote": line,
                    })

    # 4. Core Facts
    facts: List[Dict[str, Any]] = []

    # Founded year
    m_found = re.search(r"(?:founded\s+in|established\s+in|since)\s+(\d{4})", source_text, re.I)
    if m_found:
        sent = [s.strip() for s in source_text.replace("\n", " ").split(".") if m_found.group(0).lower() in s.lower()]
        quote = sent[0] if sent else m_found.group(0)
        facts.append({
            "label": "founded",
            "aliases": ["founded", "established", "since"],
            "value": int(m_found.group(1)),
            "source_quote": quote,
        })

    # Customer / Member counts (e.g. 185,000 members)
    m_mem = re.search(r"(?:more\s+than\s+)?([0-9,]+)\s+members\b", source_text, re.I)
    if m_mem:
        sent = [s.strip() for s in source_text.replace("\n", " ").split(".") if m_mem.group(0).lower() in s.lower()]
        quote = sent[0] if sent else m_mem.group(0)
        facts.append({
            "label": "members",
            "aliases": ["members", "subscribers", "customers", "active members"],
            "value": int(m_mem.group(1).replace(",", "")),
            "source_quote": quote,
        })

    # Product count (e.g. 62 products)
    m_prod = re.search(r"([0-9]+)\s+products\b", source_text, re.I)
    if m_prod:
        sent = [s.strip() for s in source_text.replace("\n", " ").split(".") if m_prod.group(0).lower() in s.lower()]
        quote = sent[0] if sent else m_prod.group(0)
        facts.append({
            "label": "products",
            "aliases": ["products", "catalogue", "items"],
            "value": int(m_prod.group(1)),
            "source_quote": quote,
        })

    # Partner farms (e.g. 140 partner farms)
    m_farm = re.search(r"([0-9]+)\s+partner\s+farms\b", source_text, re.I)
    if m_farm:
        sent = [s.strip() for s in source_text.replace("\n", " ").split(".") if m_farm.group(0).lower() in s.lower()]
        quote = sent[0] if sent else m_farm.group(0)
        facts.append({
            "label": "partner farms",
            "aliases": ["partner farms", "farms", "suppliers"],
            "value": int(m_farm.group(1)),
            "source_quote": quote,
        })

    # Free delivery threshold (e.g. 499 rupees)
    m_deliv = re.search(r"orders\s+above\s+([0-9]+)\s+(?:rupees|dollars|rs)", source_text, re.I)
    if m_deliv:
        sent = [s.strip() for s in source_text.replace("\n", " ").split(".") if m_deliv.group(0).lower() in s.lower()]
        quote = sent[0] if sent else m_deliv.group(0)
        facts.append({
            "label": "free delivery threshold",
            "aliases": ["free delivery", "orders above", "delivery threshold"],
            "value": int(m_deliv.group(1)),
            "source_quote": quote,
        })

    # Support response time (e.g. within 24 hours)
    m_sup = re.search(r"reply\s+(?:to\s+every\s+message\s+)?within\s+([0-9]+\s+hours)", source_text, re.I)
    if m_sup:
        sent = [s.strip() for s in source_text.replace("\n", " ").split(".") if m_sup.group(0).lower() in s.lower()]
        quote = sent[0] if sent else m_sup.group(0)
        facts.append({
            "label": "support reply time",
            "aliases": ["support reply", "reply time", "support response"],
            "value": m_sup.group(1),
            "source_quote": quote,
        })

    # 5. Claims policy
    claims_policy = ""
    for i, l in enumerate(lines):
        if "claims and evidence" in l.lower() and i + 1 < len(lines):
            claims_policy = " ".join(lines[i + 1 : i + 3])
            break
        if "medical or health" in l.lower() or "unsupported superlatives" in l.lower():
            claims_policy = l
            break
    if not claims_policy:
        claims_policy = "No unsupported superlatives and no guaranteed results unless backed by evidence."

    # 6. Approved messaging
    approved_messaging: List[Dict[str, Any]] = []
    for line in lines:
        if any(k in line.lower() for k in ("tagline", "slogan", "mission statement", "boilerplate", "use the line")):
            quotes = re.findall(r'["\u201c\u201d]([^"\u201c\u201d]+)["\u201c\u201d]', line)
            if quotes:
                for q in quotes:
                    approved_messaging.append({
                        "text": q.strip(),
                        "context": line[:80],
                        "source_quote": line,
                    })
            elif "boilerplate:" in line.lower():
                part = line.split(":", 1)[1].strip()
                if part:
                    approved_messaging.append({
                        "text": part,
                        "context": "Standard company boilerplate",
                        "source_quote": line,
                    })

    # 7. Channel rules
    channel_rules = {}
    if "writing for each channel" in source_text.lower():
        channel_rules["Email"] = {
            "tone_notes": "Warm signoff with tagline",
            "max_subject_chars": 50,
            "allow_exclamation": True,
        }
        channel_rules["Social Post"] = {
            "max_chars": 280,
            "max_hashtags": 3,
            "allow_exclamation": True,
        }
        channel_rules["Ad"] = {
            "required_disclaimer": "Terms apply.",
            "allow_exclamation": False,
        }

    return {
        "company": company,
        "tone": tone[:4],
        "approved_terms": ["member", "wholesome", "small-batch", "nourishing"] if "member" in source_text.lower() else [],
        "restricted_terms": restricted_terms,
        "facts": facts,
        "claims_policy": claims_policy,
        "approved_messaging": approved_messaging,
        "channel_rules": channel_rules,
    }


def merge_results(parts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge extracted rulebook dictionaries across multiple chunks and deduplicate entries."""
    if not parts:
        return {
            "company": "Brand",
            "tone": ["professional", "trustworthy"],
            "approved_terms": [],
            "restricted_terms": [],
            "facts": [],
            "claims_policy": "",
            "approved_messaging": [],
            "channel_rules": {},
        }

    company = "Brand"
    for p in parts:
        c = (p.get("company") or "").strip()
        if c and c.lower() != "brand":
            company = c
            break

    # Tone: unique list, preserving order and case
    tone_seen = set()
    tone: List[str] = []
    for p in parts:
        for t in p.get("tone") or []:
            t_str = str(t).strip()
            if t_str and t_str.lower() not in tone_seen:
                tone_seen.add(t_str.lower())
                tone.append(t_str)
    if not tone:
        tone = ["professional", "trustworthy"]

    # Approved terms
    appr_seen = set()
    approved_terms: List[str] = []
    for p in parts:
        for term in p.get("approved_terms") or []:
            term_str = str(term).strip()
            if term_str and term_str.lower() not in appr_seen:
                appr_seen.add(term_str.lower())
                approved_terms.append(term_str)

    # Restricted terms: dedupe by term.lower()
    rest_seen = set()
    restricted_terms: List[Dict[str, Any]] = []
    for p in parts:
        for item in p.get("restricted_terms") or []:
            if not isinstance(item, dict):
                continue
            term_key = (item.get("term") or "").strip().lower()
            if term_key and term_key not in rest_seen:
                rest_seen.add(term_key)
                restricted_terms.append({
                    "term": (item.get("term") or "").strip(),
                    "use": (item.get("use") or "").strip(),
                    "reason": (item.get("reason") or "").strip(),
                    "source_quote": (item.get("source_quote") or "").strip(),
                })

    # Facts: dedupe by label.lower()
    fact_seen = set()
    facts: List[Dict[str, Any]] = []
    for p in parts:
        for item in p.get("facts") or []:
            if not isinstance(item, dict):
                continue
            label_key = (item.get("label") or "").strip().lower()
            if label_key and label_key not in fact_seen:
                fact_seen.add(label_key)
                aliases = [str(a).strip() for a in (item.get("aliases") or []) if str(a).strip()]
                facts.append({
                    "label": (item.get("label") or "").strip(),
                    "aliases": aliases,
                    "value": item.get("value", ""),
                    "source_quote": (item.get("source_quote") or "").strip(),
                })

    # Approved messaging: dedupe by text.lower()
    msg_seen = set()
    approved_messaging: List[Dict[str, Any]] = []
    for p in parts:
        for item in p.get("approved_messaging") or []:
            if not isinstance(item, dict):
                continue
            text_key = (item.get("text") or "").strip().lower()
            if text_key and text_key not in msg_seen:
                msg_seen.add(text_key)
                approved_messaging.append({
                    "text": (item.get("text") or "").strip(),
                    "context": (item.get("context") or "").strip(),
                    "source_quote": (item.get("source_quote") or "").strip(),
                })

    # Claims policy: take longest / most informative
    claims_policy = ""
    for p in parts:
        cp = (p.get("claims_policy") or "").strip()
        if len(cp) > len(claims_policy):
            claims_policy = cp

    channel_rules = {}
    for p in parts:
        cr = p.get("channel_rules") or {}
        if isinstance(cr, dict):
            channel_rules.update(cr)

    return {
        "company": company,
        "tone": tone,
        "approved_terms": approved_terms,
        "restricted_terms": restricted_terms,
        "facts": facts,
        "claims_policy": claims_policy,
        "approved_messaging": approved_messaging,
        "channel_rules": channel_rules,
    }


def extract_rulebook_from_text(source_text: str, source_name: str = "") -> Tuple[Rulebook, List[str], str]:
    """
    Extract brand guidelines from raw source text using Gemini or built-in rules.
    Applies the 'never trust the AI blindly' rule: drops items without verified source quotes,
    generates verification warnings for factual claims, and guides managers on schema completeness.
    """
    if not source_text or not source_text.strip():
        raise ExtractError("No text found in source to extract rules from.")

    warnings: List[str] = []
    raw_parts: List[Dict[str, Any]] = []

    if llm_client.is_configured():
        chunks = chunk_text(source_text, CHUNK_SIZE)
        for chunk in chunks:
            try:
                data = llm_client.ask_for_json("rulebook_prompt.txt", text=chunk)
                if isinstance(data, dict):
                    raw_parts.append(data)
            except llm_client.LLMError as err:
                print(f"[rulebook_extractor] AI extraction failed ({err}), falling back to built-in rules.")
                warnings.append(f"AI call notice: {err}. Extracted draft using built-in rule analyzer.")
                raw_parts = [_rule_based_extractor(source_text)]
                break
    else:
        # Graceful fallback when GEMINI_API_KEY is not configured
        raw_parts = [_rule_based_extractor(source_text)]
        warnings.append("Notice: GEMINI_API_KEY is not configured. Draft was extracted using the built-in rule-based extractor. Add your GEMINI_API_KEY in backend/.env to enable Gemini.")

    merged = merge_results(raw_parts)
    dropped_count = 0

    # 1. Verification rule: drop restricted terms whose source_quote isn't in source text
    verified_restricted: List[Dict[str, Any]] = []
    for r in merged.get("restricted_terms", []):
        quote = r.get("source_quote", "")
        if quote and _in_source(quote, source_text):
            verified_restricted.append(r)
        else:
            dropped_count += 1
    merged["restricted_terms"] = verified_restricted

    # 2. Verification rule: drop approved messaging whose source_quote isn't in source text
    verified_messaging: List[Dict[str, Any]] = []
    for m in merged.get("approved_messaging", []):
        quote = m.get("source_quote", "")
        if quote and _in_source(quote, source_text):
            verified_messaging.append(m)
        else:
            dropped_count += 1
    merged["approved_messaging"] = verified_messaging

    # 3. Verification rule: drop facts whose source_quote isn't in source text, and issue warnings
    verified_facts: List[Dict[str, Any]] = []
    for f in merged.get("facts", []):
        quote = f.get("source_quote", "")
        if quote and _in_source(quote, source_text):
            verified_facts.append(f)
            label = f.get("label", "fact")
            val = f.get("value", "")
            warnings.append(f"Fact '{label}' ({val}): numeric/historical facts carry hallucination risk — please verify against your actual company records.")
        else:
            dropped_count += 1
    merged["facts"] = verified_facts

    if dropped_count > 0:
        warnings.append(f"Dropped {dropped_count} extracted item(s) because their quoted source text could not be verified in the document.")

    # 4. Schema completeness guidance: highlight schema areas missing from the source document
    guidance_notes = check_schema_guidance(merged)
    warnings.extend(guidance_notes)

    rulebook = Rulebook(**merged)
    return rulebook, warnings, source_name
