# content.py
# Describes content (blog, email, post...) sent to and returned from the API.

from datetime import datetime
from typing import Optional, Union

from pydantic import BaseModel, Field, model_validator


class ContentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    type: str = "Blog"                       # Blog, Email, Social Post, Landing Page, Press Release
    text: str = Field(..., min_length=1, max_length=50000)


class ContentOut(BaseModel):
    id: str = ""
    title: str = ""
    type: str = "Blog"                      # Blog, Email, Social Post, Landing Page, Press Release, Ad
    text: str = ""
    status: str = "draft"                    # draft, reviewed, pending_review, approved, changes_requested
    score: Optional[int] = None              # brand score 0-100, empty until reviewed
    owner: str = ""
    created_at: Union[str, datetime] = ""
    updated_at: Union[str, datetime] = ""

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data):
        if isinstance(data, dict):
            if not data.get("id"):
                data["id"] = str(data.get("_id", ""))
            if "type" not in data:
                data["type"] = data.get("content_type", "Blog")
            if isinstance(data.get("created_at"), datetime):
                data["created_at"] = data["created_at"].isoformat()
            if isinstance(data.get("updated_at"), datetime):
                data["updated_at"] = data["updated_at"].isoformat()
        return data


class ExtractedText(BaseModel):
    filename: str
    text: str
