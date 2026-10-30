# rulebook.py
# The brand rule book: a Brand Manager saves a new one, drafts one with AI, or reads the active one.

from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from app.config import MAX_UPLOAD_MB
from app.database import rulebooks
from app.routes.auth import get_current_user, require_role
from app.schemas import to_dict
from app.schemas.rulebook import ExtractOut, Rulebook, RulebookOut
from app.services.audit_service import log_event
from app.services.review_service import now
from app.services.rulebook_extractor import extract_rulebook_from_text, fetch_url_text
from app.services.text_extractor import ExtractError, extract_text

router = APIRouter(prefix="/rulebook", tags=["rulebook"])


def _active():
    """The currently active rule book (without MongoDB's internal fields), or None."""
    return rulebooks.find_one({"active": True}, {"_id": 0, "active": 0})


@router.post("", response_model=RulebookOut)
def save_rulebook(body: Rulebook, user=Depends(require_role("manager"))):
    """Save a new rule book and make it the active one (older ones are kept but switched off)."""
    import re

    highest_v = 0
    for doc in rulebooks.find({}, {"version": 1}):
        raw_v = doc.get("version")
        if isinstance(raw_v, int):
            if raw_v > highest_v:
                highest_v = raw_v
        elif isinstance(raw_v, str):
            m = re.search(r"\d+", raw_v)
            if m:
                val = int(m.group(0))
                if val > highest_v:
                    highest_v = val
        elif isinstance(raw_v, float):
            val = int(raw_v)
            if val > highest_v:
                highest_v = val

    next_version = highest_v + 1
    new_id = uuid4().hex

    rulebooks.update_many({}, {"$set": {"active": False}})
    doc = {
        **to_dict(body),
        "rulebook_id": new_id,
        "version": next_version,
        "active": True,
        "updated": now(),
        "uploaded_by": user["name"],
    }
    rulebooks.insert_one(doc)
    log_event(new_id, "rulebook_saved", user, {"version": next_version, "company": body.company})
    return _active()


@router.get("/active", response_model=RulebookOut)
def get_active_rulebook(user=Depends(get_current_user)):
    rulebook = _active()
    if not rulebook:
        raise HTTPException(status_code=404, detail="No rule book has been uploaded yet.")
    return rulebook


@router.post("/extract", response_model=ExtractOut)
async def extract_rulebook(
    request: Request,
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    user=Depends(require_role("manager")),
):
    """
    Feature 1: Auto-extract brand rules from an uploaded file (.pdf, .docx, .txt) or fetched URL.
    Returns a draft rulebook in the standard schema, accompanied by verification warnings.
    Nothing is saved directly — the Manager reviews and saves with 'Save as active'.
    """
    content_type = request.headers.get("content-type", "")
    target_url = url

    # Support JSON requests with { "url": "..." }
    if "application/json" in content_type:
        try:
            body = await request.json()
            if isinstance(body, dict):
                target_url = body.get("url") or target_url
        except Exception:
            pass

    source_name = ""
    raw_text = ""

    if file and file.filename:
        data = await file.read()
        if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
            raise HTTPException(status_code=413, detail=f"File exceeds size limit of {MAX_UPLOAD_MB} MB.")
        try:
            raw_text = extract_text(file.filename, data)
        except ExtractError as err:
            raise HTTPException(status_code=400, detail=str(err))
        source_name = file.filename
    elif target_url and target_url.strip():
        try:
            raw_text = fetch_url_text(target_url.strip())
        except ExtractError as err:
            raise HTTPException(status_code=400, detail=str(err))
        source_name = target_url.strip()
    else:
        raise HTTPException(
            status_code=400,
            detail="Please provide a guidelines file (.pdf, .docx, .txt) or a web page URL to extract from.",
        )

    if not raw_text or not raw_text.strip():
        raise HTTPException(status_code=400, detail="No readable text could be extracted from the provided source.")

    try:
        draft, warnings, source = extract_rulebook_from_text(raw_text, source_name=source_name)
    except ExtractError as err:
        raise HTTPException(status_code=400, detail=str(err))

    return ExtractOut(draft=draft, warnings=warnings, source=source)
