import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..auth.deps import CurrentUser, current_user
from ..config import get_settings
from ..db import Feedback, audit, session
from ..guardrails.images import ImageRejected, sanitize_data_url
from ..guardrails.ratelimit import RateLimiter
from ..llm import orchestrator
from ..llm.titling import generate_title
from ..llm.openrouter import LLMError, LLMQuotaError

router = APIRouter(tags=["chat"])
_limiter = RateLimiter(get_settings().chat_per_minute)


class TitleIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


@router.post("/chat/title")
async def chat_title(body: TitleIn, user: CurrentUser = Depends(current_user)):
    _limiter.check(user.email)
    try:
        title = await generate_title(user.email, body.question)
    except LLMError:
        raise HTTPException(503, "Could not name this chat right now.") from None
    if not title:
        raise HTTPException(503, "Could not name this chat right now.")
    return {"title": title}


class Msg(BaseModel):
    role: str
    content: str = Field(max_length=20000)


class PageContext(BaseModel):
    title: str = Field(default="", max_length=300)
    url: str = Field(default="", max_length=1000)
    selection: str = Field(default="", max_length=4000)


class Attachment(BaseModel):
    name: str = Field(max_length=160)
    text: str = Field(max_length=30000)


class ChatIn(BaseModel):
    messages: list[Msg] = Field(min_length=1, max_length=60)
    page_context: PageContext | None = None
    images: list[str] = []
    files: list[Attachment] = []


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat")
async def chat(body: ChatIn, user: CurrentUser = Depends(current_user)):
    s = get_settings()
    _limiter.check(user.email)
    if body.messages[-1].role != "user" or not body.messages[-1].content.strip():
        raise HTTPException(400, "The last message must be a non-empty user message.")
    if len(body.messages[-1].content) > s.max_message_chars:
        raise HTTPException(413, f"Messages are limited to {s.max_message_chars} characters.")
    if len(body.images) > s.max_images:
        raise HTTPException(400, f"You can attach up to {s.max_images} images.")
    try:
        images = [sanitize_data_url(u) for u in body.images]
    except ImageRejected as e:
        raise HTTPException(400, str(e)) from e

    if len(body.files) > s.max_files:
        raise HTTPException(400, f"You can attach up to {s.max_files} files.")
    files = [f.model_dump() for f in body.files]
    msgs = [m.model_dump() for m in body.messages]
    ctx = body.page_context.model_dump() if body.page_context else None
    audit(user.email, "chat", f"turns={len(msgs)} images={len(images)} files={len(files)} page_ctx={bool(ctx)}")
    queue: asyncio.Queue = asyncio.Queue()

    async def emit(ev: dict):
        await queue.put((ev.get("type", "status"), {k: v for k, v in ev.items() if k != "type"}))

    async def worker():
        try:
            result = await orchestrator.run_chat(user.email, msgs, ctx, images, emit, files=files)
            await queue.put(("result", result))
        except LLMQuotaError:
            await queue.put(("error", {"message": "The OpenRouter API key has reached its spending limit. Update its limit or use another key in the server settings."}))
        except LLMError as e:
            await queue.put(("error", {"message": "The AI service had a problem. Please try again in a moment.", "detail": str(e)[:200]}))
        except Exception as e:
            await queue.put(("error", {"message": "Something went wrong on the server.", "detail": type(e).__name__}))
        finally:
            await queue.put(("end", {}))

    task = asyncio.create_task(worker())

    async def stream():
        try:
            while True:
                kind, data = await queue.get()
                if kind == "end":
                    break
                if kind == "result":
                    text = data["answer"]

                    for i in range(0, len(text), 40):
                        yield sse("delta", {"text": text[i:i + 40]})
                        await asyncio.sleep(0.008)
                    yield sse("done", {k: v for k, v in data.items() if k != "answer"} | {"answer": text})
                else:
                    yield sse(kind, data)
        finally:
            task.cancel()

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


class FeedbackIn(BaseModel):
    rating: str = Field(pattern="^(up|down)$")
    comment: str = Field(default="", max_length=500)


@router.post("/feedback")
def feedback(body: FeedbackIn, user: CurrentUser = Depends(current_user)):
    with session() as db:
        db.add(Feedback(user_email=user.email, rating=body.rating, comment=body.comment))
        db.commit()
    return {"ok": True}
