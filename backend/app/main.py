import contextlib

import jwt
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth.sessions import verify_session, verify_state
from .auth.google import session_email_allowed
from .canvas import oauth
from .config import get_settings
from .db import get_engine, purge_old_audit
from .mcp.canvas_server import mcp as canvas_mcp
from .mcp.context import current_user_email
from .mcp.knowledge_server import mcp as knowledge_mcp
from .routes import admin, auth, canvas, chat, sources, uploads


class McpAuth:
    """ASGI wrapper for the mounted MCP HTTP endpoints. Accepts a short-lived internal token or a normal Esolv session."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        hdr = dict(scope["headers"]).get(b"authorization", b"").decode()
        email = None
        if hdr.lower().startswith("bearer "):
            tok = hdr[7:]
            for fn in (lambda t: verify_state(t, "mcp"), lambda t: verify_session(t)["sub"]):
                try:
                    email = fn(tok)
                    break
                except jwt.PyJWTError:
                    continue
        if not email or not session_email_allowed(email):
            await send({"type": "http.response.start", "status": 401, "headers": [(b"content-type", b"application/json")]})
            await send({"type": "http.response.body", "body": b'{"error":"unauthorized"}'})
            return
        token = current_user_email.set(email)
        try:
            await self.app(scope, receive, send)
        finally:
            current_user_email.reset(token)


_canvas_app = canvas_mcp.streamable_http_app()
_knowledge_app = knowledge_mcp.streamable_http_app()


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    get_engine()
    purge_old_audit()
    async with contextlib.AsyncExitStack() as stack:
        await stack.enter_async_context(canvas_mcp.session_manager.run())
        await stack.enter_async_context(knowledge_mcp.session_manager.run())
        yield


def create_app() -> FastAPI:
    app = FastAPI(title="Esolv API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^(chrome-extension://[a-z]{32}|http://(localhost|127\.0\.0\.1)(:\d+)?)$",
        allow_methods=["*"], allow_headers=["*"],
    )

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/config")
    def public_config():
        s = get_settings()
        return {"google_client_id": s.google_client_id, "allowed_domains": s.allowed_domain_list,
                "dev_login": s.dev_login and not s.is_prod, "model": s.openrouter_model,
                "canvas_oauth": bool(s.canvas_client_id), "canvas_base_url": s.canvas_base_url}

    for r in (auth.router, canvas.router, oauth.router, chat.router, uploads.router, admin.router, sources.router):
        app.include_router(r)
    app.mount("/mcp/canvas", McpAuth(_canvas_app))
    app.mount("/mcp/knowledge", McpAuth(_knowledge_app))
    return app


app = create_app()
