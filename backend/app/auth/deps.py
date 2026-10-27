import jwt
from fastapi import Depends, Header, HTTPException

from ..config import get_settings
from .google import session_email_allowed
from .sessions import verify_session


class CurrentUser(dict):
    @property
    def email(self) -> str:
        return self["sub"]

    @property
    def is_admin(self) -> bool:
        return self.email in get_settings().admin_list


def current_user(authorization: str = Header(default="")) -> CurrentUser:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Not signed in")
    try:
        claims = verify_session(authorization[7:])
    except jwt.PyJWTError as e:
        raise HTTPException(401, "Session expired, please sign in again") from e
    if not session_email_allowed(claims.get("sub", "")):
        raise HTTPException(403, "Esolv is only available to approved accounts.")
    return CurrentUser(claims)


def admin_user(user: CurrentUser = Depends(current_user)) -> CurrentUser:
    if not user.is_admin:
        raise HTTPException(403, "Admin only")
    return user
