from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth.deps import CurrentUser, current_user
from ..auth.google import session_email_allowed, verify_google_token
from ..auth.sessions import issue_session
from ..config import get_settings
from ..db import User, audit, session, utcnow

router = APIRouter(tags=["auth"])


class GoogleIn(BaseModel):
    id_token: str


class DevIn(BaseModel):
    email: str
    name: str = "Dev Teacher"


def _login(email: str, name: str, picture: str) -> dict:
    email = email.lower()
    with session() as db:
        u = db.get(User, email) or User(email=email)
        u.name, u.picture, u.last_login = name or u.name, picture or u.picture, utcnow()
        db.add(u)
        db.commit()
    token, exp = issue_session(email, name, picture)
    audit(email, "login")
    return {"token": token, "expires_at": exp, "user": {"email": email, "name": name, "picture": picture, "is_admin": email in get_settings().admin_list}}


@router.post("/auth/google")
async def google_login(body: GoogleIn):
    claims = await verify_google_token(body.id_token)
    return _login(claims["email"], claims.get("name", ""), claims.get("picture", ""))


@router.post("/auth/dev")
async def dev_login(body: DevIn):
    s = get_settings()
    if not s.dev_login or s.is_prod:
        raise HTTPException(404, "Not found")
    if not session_email_allowed(body.email):
        raise HTTPException(403, "Esolv is only available to approved accounts.")
    return _login(body.email, body.name, "")


@router.get("/me")
def me(user: CurrentUser = Depends(current_user)):
    return {"email": user.email, "name": user.get("name", ""), "picture": user.get("picture", ""), "is_admin": user.is_admin}
