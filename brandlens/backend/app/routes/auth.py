# auth.py
# Demo login for the three roles (creator, manager, reviewer) and the helpers that check who is calling.
# There are no passwords: this is a hackathon demo. Anyone can pick a role, so do not put real secrets behind it.

from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.config import JWT_HOURS, JWT_SECRET

router = APIRouter(prefix="/auth", tags=["auth"])

ROLES = ("creator", "manager", "reviewer")


class LoginIn(BaseModel):
    role: str
    name: str = ""


@router.post("/login")
def login(body: LoginIn):
    """Choose a role and a name; get back a signed token the frontend sends with every request."""
    if body.role not in ROLES:
        raise HTTPException(status_code=400, detail=f"Role must be one of: {', '.join(ROLES)}")

    name = body.name.strip() or "Demo User"
    payload = {
        "sub": name,
        "role": body.role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_HOURS),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    return {"token": token, "role": body.role, "name": name}


def get_current_user(authorization: Optional[str] = Header(default=None)):
    """Read 'Authorization: Bearer <token>' and return {"name", "role"}. Answers 401 if it is missing or invalid."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Please log in first.")
    token = authorization[7:].strip()
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Your login has expired. Please log in again.")
    return {"name": data.get("sub", ""), "role": data.get("role", "")}


def require_role(*allowed):
    """Use as Depends(require_role("creator")) to let only those roles call an endpoint (403 for others)."""

    def checker(user=Depends(get_current_user)):
        if user["role"] not in allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Only {' / '.join(allowed)} can do this. You are logged in as {user['role']}.",
            )
        return user

    return checker
