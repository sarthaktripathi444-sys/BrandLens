# content.py
# Creating and reading content (blog, email, social post...). Reviewing it happens in routes/review.py.

from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from uuid import uuid4

from app.config import MAX_UPLOAD_MB
from app.database import contents, strip_id
from app.routes.auth import get_current_user, require_role
from app.schemas.content import ContentCreate, ContentOut, ExtractedText
from app.services.review_service import now
from app.services.text_extractor import ExtractError, extract_text

router = APIRouter(prefix="/content", tags=["content"])


@router.post("", response_model=ContentOut, status_code=201)
def create_content(body: ContentCreate, user=Depends(require_role("creator"))):
    """Save new content as a draft. The AI review is started separately (POST /review/{id}/run)."""
    title, text = body.title.strip(), body.text.strip()
    if not title or not text:
        raise HTTPException(status_code=400, detail="Please add a title and some content first.")

    stamp = now()
    doc = {
        "id": uuid4().hex,
        "title": title,
        "type": body.type,
        "text": text,
        "status": "draft",
        "score": None,
        "owner": user["name"],
        "created_at": stamp,
        "updated_at": stamp,
    }
    contents.insert_one(doc)
    return strip_id(doc)


@router.post("/extract", response_model=ExtractedText)
async def extract_file_text(file: UploadFile = File(...), user=Depends(require_role("creator"))):
    """Read the text out of an uploaded .txt, .pdf or .docx file (nothing is saved)."""
    data = await file.read()
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File is too large (limit {MAX_UPLOAD_MB} MB).")
    try:
        text = extract_text(file.filename, data)
    except ExtractError as error:
        raise HTTPException(status_code=400, detail=str(error))
    if not text:
        raise HTTPException(status_code=400, detail="No readable text was found in this file.")
    return {"filename": file.filename or "", "text": text}


@router.get("", response_model=List[ContentOut])
def list_content(user=Depends(get_current_user)):
    """All content, newest first."""
    return list(contents.find({}, {"_id": 0}).sort("created_at", -1))


@router.get("/{content_id}", response_model=ContentOut)
def get_content(content_id: str, user=Depends(get_current_user)):
    doc = contents.find_one({"id": content_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Content not found.")
    return doc
