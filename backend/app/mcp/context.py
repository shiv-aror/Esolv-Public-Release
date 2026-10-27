"""Per-request identity for MCP tool calls (set by the orchestrator or the HTTP auth middleware)."""
from contextvars import ContextVar

current_user_email: ContextVar[str | None] = ContextVar("current_user_email", default=None)


def require_user() -> str:
    email = current_user_email.get()
    if not email:
        raise PermissionError("No authenticated user for this tool call")
    return email
