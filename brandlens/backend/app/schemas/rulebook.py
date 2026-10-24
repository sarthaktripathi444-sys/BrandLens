# rulebook.py
# Describes the shape of the brand rule book JSON that the Brand Manager uploads.

from typing import List, Optional, Union

from pydantic import BaseModel


class RestrictedTerm(BaseModel):
    term: str          # the word to avoid, e.g. "user"
    use: str           # the word to use instead, e.g. "customer"
    reason: str = ""   # why, shown to the creator


class Fact(BaseModel):
    label: str                  # e.g. "active customers"
    aliases: List[str] = []     # other words the content may use, e.g. ["customers", "clients", "users"]
    value: Union[int, float, str]  # the true value, e.g. 14000 or 2019


class Rulebook(BaseModel):
    company: str
    tone: List[str]
    approved_terms: List[str] = []
    restricted_terms: List[RestrictedTerm] = []
    facts: List[Fact] = []
    claims_policy: str = ""


class RulebookOut(Rulebook):
    # Extra field added when the rule book is read back.
    updated: Optional[str] = None
