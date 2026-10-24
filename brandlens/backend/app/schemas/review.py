# review.py
# Describes a Finding (one flag), the full review sent to the frontend, and the requests that change it.

from typing import List, Optional
from typing import Literal

from pydantic import BaseModel


class Finding(BaseModel):
    id: str
    category: str                 # terminology, tone, fact or claim
    text: str                     # the exact flagged words
    start: Optional[int] = None   # where the flagged words begin / end in the content
    end: Optional[int] = None
    issue: str                    # short title of the problem
    reason: str                   # why it is a problem
    rule: str                     # which brand rule it breaks
    suggestion: str = ""          # replacement wording; empty means "fix by hand"
    status: str = "pending"       # pending, accepted or rejected
    source: str = "rule"          # "rule" (built-in check) or "ai" (Gemini)


class ReviewOut(BaseModel):
    content_id: str
    title: str
    type: str
    text: str                     # the original content
    revised_text: str             # the content with all ACCEPTED fixes applied
    score: Optional[int] = None
    status: str                   # the content's status
    findings: List[Finding]
    comment: Optional[str] = None       # reviewer's comment, if any
    reviewed_by: Optional[str] = None


class FindingStatusIn(BaseModel):
    status: Literal["pending", "accepted", "rejected"]


class RunReviewIn(BaseModel):
    # True = first replace the text with the accepted fixes, then review again.
    apply_accepted: bool = False


class DecisionIn(BaseModel):
    decision: Literal["approved", "changes_requested"]
    comment: str = ""
