import asyncio

from fastapi import APIRouter, Depends

from ..auth.deps import CurrentUser, admin_user
from ..db import audit
from ..rag import ingest, store

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/ingest")
async def reingest(user: CurrentUser = Depends(admin_user)):
    stats = await asyncio.to_thread(ingest.run)
    audit(user.email, "admin.ingest", f"docs={stats['documents']} chunks={stats['chunks']}")
    return stats


@router.get("/stats")
def stats(user: CurrentUser = Depends(admin_user)):
    return {"chunks": store.count()}
