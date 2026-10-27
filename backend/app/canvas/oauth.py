from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse

from ..auth.deps import CurrentUser, current_user
from ..auth.sessions import issue_state, verify_state
from ..config import get_settings
from ..db import audit
from . import tokens

router = APIRouter(prefix="/canvas/oauth", tags=["canvas"])


@router.get("/start")
def start(user: CurrentUser = Depends(current_user)):
    s = get_settings()
    if not (s.canvas_client_id and s.canvas_client_secret):
        raise HTTPException(501, "Canvas OAuth is not configured. Ask your admin for a Canvas Developer Key, or use a personal access token.")
    params = {
        "client_id": s.canvas_client_id, "response_type": "code", "redirect_uri": s.canvas_redirect_uri,
        "state": issue_state(user.email, "canvas-oauth"),
    }
    if s.canvas_oauth_scopes.strip():
        params["scope"] = s.canvas_oauth_scopes.strip()
    return {"url": f"{s.canvas_base_url}/login/oauth2/auth?{urlencode(params)}"}


@router.get("/callback", response_class=HTMLResponse)
async def callback(code: str = "", state: str = "", error: str = ""):
    s = get_settings()
    if error or not code:
        return HTMLResponse(_page("Canvas connection cancelled", "You can close this tab and try again from Esolv."), 400)
    try:
        email = verify_state(state, "canvas-oauth")
    except Exception:
        return HTMLResponse(_page("Link expired", "Please start the connection again from Esolv."), 400)
    async with httpx.AsyncClient(timeout=20) as h:
        r = await h.post(f"{s.canvas_base_url}/login/oauth2/token", data={
            "grant_type": "authorization_code", "client_id": s.canvas_client_id,
            "client_secret": s.canvas_client_secret, "redirect_uri": s.canvas_redirect_uri, "code": code,
        })
    if r.status_code != 200:
        return HTMLResponse(_page("Canvas said no", "Canvas rejected the sign-in. Please try again."), 400)
    d = r.json()
    tokens.save_credential(email, "oauth", d["access_token"], d.get("refresh_token", ""), d.get("expires_in"))
    audit(email, "canvas.connect", "oauth")
    return HTMLResponse(_page("Canvas connected ✓", "You can close this tab and return to Esolv."))


def _page(title: str, msg: str) -> str:
    return f"""<!doctype html><meta charset=utf-8><title>{title}</title>
<body style="font:16px -apple-system,system-ui,sans-serif;display:grid;place-items:center;height:100vh;margin:0;background:#faf9f7;color:#1f1d1a">
<div style="text-align:center"><h1 style="font-weight:600">{title}</h1><p style="color:#6b665e">{msg}</p></div></body>"""
