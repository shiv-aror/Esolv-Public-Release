"""Validate + sanitize teacher-supplied images: type/size checks, EXIF/metadata stripped, downscaled, re-encoded."""
import base64
import binascii
import io
import re

from PIL import Image, ImageOps

from ..config import get_settings

_ALLOWED = {"PNG", "JPEG", "WEBP"}
_DATA_URL = re.compile(r"^data:(image/(?:png|jpeg|jpg|webp));base64,(.+)$", re.DOTALL)
MAX_DIM = 1568


class ImageRejected(ValueError):
    pass


def sanitize_data_url(data_url: str) -> str:
    s = get_settings()
    m = _DATA_URL.match(data_url or "")
    if not m:
        raise ImageRejected("Only PNG, JPEG or WebP images can be attached.")
    try:
        raw = base64.b64decode(m.group(2), validate=False)
    except (binascii.Error, ValueError) as e:
        raise ImageRejected("The image data was corrupted.") from e
    if len(raw) > s.max_image_bytes:
        raise ImageRejected(f"Images must be under {s.max_image_bytes // (1024 * 1024)} MB.")
    try:
        im = Image.open(io.BytesIO(raw))
        fmt = im.format
        im.verify()
        im = Image.open(io.BytesIO(raw))
    except Exception as e:
        raise ImageRejected("That file isn't a valid image.") from e
    if fmt not in _ALLOWED:
        raise ImageRejected("Only PNG, JPEG or WebP images can be attached.")
    im = ImageOps.exif_transpose(im)
    im.thumbnail((MAX_DIM, MAX_DIM))
    has_alpha = im.mode in ("RGBA", "LA", "P")
    buf = io.BytesIO()
    if has_alpha:
        im.convert("RGBA").save(buf, "PNG", optimize=True)
        mime = "image/png"
    else:
        im.convert("RGB").save(buf, "JPEG", quality=85, optimize=True)
        mime = "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(buf.getvalue()).decode()}"
