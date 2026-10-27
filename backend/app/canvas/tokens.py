"""Resolve a CanvasClient for a user from their stored (encrypted) PAT or OAuth credential."""
from datetime import timezone, timedelta

import httpx

from .. import security
from ..config import get_settings
from ..db import CanvasCredential, session, utcnow
from .client import CanvasAuthError, CanvasClient
from .mock import MockCanvasClient


class NotConnected(Exception):
    pass


def save_credential(email: str, kind: str, access: str, refresh: str = "", expires_in: int | None = None) -> None:
    s = get_settings()
    with session() as db:
        cred = db.get(CanvasCredential, email) or CanvasCredential(user_email=email)
        cred.kind, cred.base_url = kind, s.canvas_base_url
        cred.access_enc = security.encrypt(access)
        cred.refresh_enc = security.encrypt(refresh) if refresh else ""
        cred.expires_at = utcnow() + timedelta(seconds=expires_in) if expires_in else None
        cred.updated_at = utcnow()
        db.add(cred)
        db.commit()


def delete_credential(email: str) -> None:
    with session() as db:
        cred = db.get(CanvasCredential, email)
        if cred:
            db.delete(cred)
            db.commit()


def status(email: str) -> dict:
    with session() as db:
        cred = db.get(CanvasCredential, email)
    if cred:
        return {"connected": True, "kind": cred.kind, "base_url": cred.base_url, "mock": False}
    if get_settings().canvas_mock:
        return {"connected": True, "kind": "mock", "base_url": "", "mock": True}
    return {"connected": False, "kind": None, "base_url": get_settings().canvas_base_url, "mock": False}


async def _refresh(cred: CanvasCredential) -> str:
    s = get_settings()
    async with httpx.AsyncClient(timeout=20) as h:
        r = await h.post(f"{cred.base_url}/login/oauth2/token", data={
            "grant_type": "refresh_token", "client_id": s.canvas_client_id,
            "client_secret": s.canvas_client_secret, "refresh_token": security.decrypt(cred.refresh_enc),
        })
    if r.status_code != 200:
        raise CanvasAuthError("Canvas sign-in expired. Reconnect Canvas in Settings.")
    data = r.json()
    save_credential(cred.user_email, "oauth", data["access_token"], security.decrypt(cred.refresh_enc), data.get("expires_in"))
    return data["access_token"]


async def get_client(email: str) -> CanvasClient | MockCanvasClient:
    with session() as db:
        cred = db.get(CanvasCredential, email)
    if cred is None:
        if get_settings().canvas_mock:
            return MockCanvasClient()
        raise NotConnected("Canvas is not connected. Open Settings and connect Canvas first.")
    token = security.decrypt(cred.access_enc)
    exp = cred.expires_at.replace(tzinfo=timezone.utc) if cred.expires_at and cred.expires_at.tzinfo is None else cred.expires_at
    if cred.kind == "oauth" and exp and exp <= utcnow() + timedelta(seconds=60) and cred.refresh_enc:
        token = await _refresh(cred)
    return CanvasClient(cred.base_url, token)
