from typing import Dict, List, Optional, Union
from pydantic import BaseModel


class RestrictedTerm(BaseModel):
    term: str
    use: str
    reason: str = ""
    source_quote: str = ""          # NEW: where the extractor found it (optional)


class Fact(BaseModel):
    label: str
    aliases: List[str] = []
    value: Union[int, float, str]
    source_quote: str = ""          # NEW


class ApprovedMessage(BaseModel):   # NEW: a line the brand likes to use
    text: str
    context: str = ""
    source_quote: str = ""


class ChannelRule(BaseModel):       # NEW: extra rules for one channel
    tone_notes: str = ""
    max_chars: Optional[int] = None
    max_subject_chars: Optional[int] = None   # emails
    allow_exclamation: bool = True
    max_hashtags: Optional[int] = None
    required_disclaimer: str = ""


class Rulebook(BaseModel):
    company: str
    tone: List[str]
    approved_terms: List[str] = []
    restricted_terms: List[RestrictedTerm] = []
    facts: List[Fact] = []
    claims_policy: str = ""
    approved_messaging: List[ApprovedMessage] = []        # NEW
    channel_rules: Dict[str, ChannelRule] = {}            # NEW: {"Email": {...}, "Ad": {...}}


class RulebookOut(Rulebook):
    updated: Optional[str] = None
    rulebook_id: str = ""     # NEW: set by the server on save (Person A)
    version: int = 0          # NEW: 1, 2, 3... on each save (Person A)