from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth.deps import CurrentUser, current_user
from ..canvas import roster, tokens
from ..canvas.client import CanvasClient, CanvasError
from ..config import get_settings
from ..db import audit

router = APIRouter(prefix="/canvas", tags=["canvas"])


class TokenIn(BaseModel):
    token: str = Field(min_length=10, max_length=300)


@router.get("/status")
def status(user: CurrentUser = Depends(current_user)):
    s = get_settings()
    return {**tokens.status(user.email), "oauth_available": bool(s.canvas_client_id and s.canvas_client_secret),
            "canvas_base_url": s.canvas_base_url}


@router.post("/token")
async def set_token(body: TokenIn, user: CurrentUser = Depends(current_user)):
    s = get_settings()
    client = CanvasClient(s.canvas_base_url, body.token.strip())
    try:
        me = await client.whoami()
    except CanvasError as e:
        raise HTTPException(400, "Canvas didn't accept that token. Check that you copied it fully.") from e
    finally:
        await client.aclose()
    tokens.save_credential(user.email, "pat", body.token.strip())
    roster.clear(user.email)
    audit(user.email, "canvas.connect", "pat")
    return {"connected": True, "canvas_name": me.get("name", "")}


@router.delete("/token")
def remove_token(user: CurrentUser = Depends(current_user)):
    tokens.delete_credential(user.email)
    roster.clear(user.email)
    audit(user.email, "canvas.disconnect")
    return {"connected": False}
