# rulebook.py
# The brand rule book: a Brand Manager saves a new one, everyone can read the active one.

from fastapi import APIRouter, Depends, HTTPException

from app.database import rulebooks
from app.routes.auth import get_current_user, require_role
from app.schemas import to_dict
from app.schemas.rulebook import Rulebook, RulebookOut
from app.services.review_service import now

router = APIRouter(prefix="/rulebook", tags=["rulebook"])


def _active():
    """The currently active rule book (without MongoDB's internal fields), or None."""
    return rulebooks.find_one({"active": True}, {"_id": 0, "active": 0})


@router.post("", response_model=RulebookOut)
def save_rulebook(body: Rulebook, user=Depends(require_role("manager"))):
    """Save a new rule book and make it the active one (older ones are kept but switched off)."""
    rulebooks.update_many({}, {"$set": {"active": False}})
    rulebooks.insert_one({**to_dict(body), "active": True, "updated": now(), "uploaded_by": user["name"]})
    return _active()


@router.get("/active", response_model=RulebookOut)
def get_active_rulebook(user=Depends(get_current_user)):
    rulebook = _active()
    if not rulebook:
        raise HTTPException(status_code=404, detail="No rule book has been uploaded yet.")
    return rulebook
