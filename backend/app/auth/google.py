import asyncio
import logging

from fastapi import HTTPException
from google.auth.transport import requests as g_requests
from google.auth import exceptions as g_exceptions
from google.oauth2 import id_token as g_id_token

from ..config import get_settings

log = logging.getLogger(__name__)


def _token_error(reason: str) -> tuple[str, str]:
    reason = reason.lower()
    if "audience" in reason:
        return "wrong_audience", "Google sign-in used a different OAuth client. Reload Esolv and try again."
    if "expired" in reason:
        return "expired", "Google sign-in took too long. Please try again."
    if "too early" in reason:
        return "clock_skew", "Your computer or server clock appears out of sync. Check its date and time, then try again."
    if "signature" in reason or "certificate" in reason:
        return "signature", "Google could not verify this sign-in token. Please try again."
    if "issuer" in reason:
        return "issuer", "Google returned a token from an unexpected issuer. Please try again."
    return "invalid", "Google could not verify the sign-in token. Please try again."


def domain_allowed(email: str, hd: str | None) -> bool:
    s = get_settings()
    normalized = email.strip().lower()
    if normalized in s.allowed_email_list:
        return True
    domains = s.allowed_domain_list
    email_domain = normalized.rsplit("@", 1)[-1] if "@" in normalized else ""

    return email_domain in domains and (hd or "").lower() in domains


def session_email_allowed(email: str) -> bool:
    """A session was issued only after Google token verification; re-check its email on every request."""
    s = get_settings()
    normalized = email.strip().lower()
    return normalized in s.allowed_email_list or normalized.rsplit("@", 1)[-1] in s.allowed_domain_list


def _verify_sync(token: str) -> dict:
    s = get_settings()
    return g_id_token.verify_oauth2_token(
        token, g_requests.Request(), s.google_client_id, clock_skew_in_seconds=60
    )


async def verify_google_token(token: str) -> dict:
    s = get_settings()
    if not s.google_client_id:
        raise HTTPException(503, "Google sign-in is not configured on the server (GOOGLE_CLIENT_ID).")
    if token.count(".") != 2:
        raise HTTPException(401, "Invalid Google token.")
    try:
        claims = await asyncio.to_thread(_verify_sync, token)
    except ValueError as e:
        category, message = _token_error(str(e))
        log.warning("Google ID token rejected: %s", category)
        raise HTTPException(401, message) from e
    except g_exceptions.TransportError as e:
        raise HTTPException(503, "Google verification is temporarily unavailable.") from e
    if not claims.get("email_verified"):
        raise HTTPException(401, "Google email is not verified.")
    if not domain_allowed(claims.get("email", ""), claims.get("hd")):
        raise HTTPException(403, "Esolv is only available to approved accounts.")
    return claims
