# content.py
# Describes content (blog, email, post...) sent to and returned from the API.

from typing import Optional

from pydantic import BaseModel, Field


class ContentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    type: str = "Blog"                       # Blog, Email, Social Post, Landing Page, Press Release
    text: str = Field(..., min_length=1, max_length=50000)


class ContentOut(BaseModel):
    id: str
    title: str
    type: str
    text: str
    status: str                              # draft, reviewed, pending_review, approved, changes_requested
    score: Optional[int] = None              # brand score 0-100, empty until reviewed
    owner: str = ""
    created_at: str = ""
    updated_at: str = ""


class ExtractedText(BaseModel):
    filename: str
    text: str
