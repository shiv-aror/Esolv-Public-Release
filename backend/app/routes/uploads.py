from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ..auth.deps import CurrentUser, current_user
from ..config import get_settings
from ..db import audit
from ..guardrails import files as file_guard
from ..guardrails.images import ImageRejected, sanitize_data_url
import asyncio
import base64

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("/image")
async def upload_image(file: UploadFile = File(...), user: CurrentUser = Depends(current_user)):
    """Validate + sanitize an image and return it as a data URL ready to attach to /chat. Nothing is stored."""
    raw = await file.read(get_settings().max_image_bytes + 1)
    mime = file.content_type or "image/png"
    try:
        url = sanitize_data_url(f"data:{mime};base64,{base64.b64encode(raw).decode()}")
    except ImageRejected as e:
        raise HTTPException(400, str(e)) from e
    return {"data_url": url, "bytes": len(url) * 3 // 4}


@router.post("/file")
async def upload_file(file: UploadFile = File(...), user: CurrentUser = Depends(current_user)):
    """Extract readable text from a PDF/Word/text file so it can be attached to the next chat message. Nothing is stored."""
    raw = await file.read(get_settings().max_file_bytes + 1)
    try:
        out = await asyncio.to_thread(file_guard.extract, file.filename or "file", raw)
    except file_guard.FileRejected as e:
        raise HTTPException(400, str(e)) from e
    audit(user.email, "upload.file", f"ext={out['name'].rsplit('.', 1)[-1].lower()} chars={out['chars']}")
    return out
