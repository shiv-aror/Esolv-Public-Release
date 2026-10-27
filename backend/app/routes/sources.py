from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from ..auth.deps import CurrentUser, current_user
from ..config import get_settings
from ..security import verify_signed

router = APIRouter(tags=["sources"])


@router.get("/sources/file/{filename}")
def source_file(filename: str, exp: int, sig: str):
    """Signed, expiring link so a citation chip can open a locally-hosted source without sending auth headers."""
    path = f"/sources/file/{filename}"
    if not verify_signed(path, exp, sig):
        raise HTTPException(403, "This link has expired. Ask the question again to get a fresh one.")
    docs = get_settings().docs_dir.resolve()
    p = (docs / filename).resolve()
    if docs not in p.parents or not p.is_file():
        raise HTTPException(404, "Not found")
    return FileResponse(p, filename=p.name, media_type="text/plain; charset=utf-8" if p.suffix in {".md", ".txt"} else None)


@router.get("/sources")
def list_sources(user: CurrentUser = Depends(current_user)):
    from ..rag import store
    docs: dict[str, dict] = {}
    for c in store.all_chunks():
        docs.setdefault(c.doc_id, {"title": c.title, "doc_type": c.doc_type, "url": c.url})
    return {"documents": sorted(docs.values(), key=lambda d: d["title"])}
