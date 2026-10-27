"""Symmetric encryption for stored Canvas credentials + signed-URL helpers."""
import base64
import hashlib
import hmac
import time

from cryptography.fernet import Fernet

from .config import get_settings


def _fernet() -> Fernet:
    key = get_settings().encryption_key
    if not key:

        key = base64.urlsafe_b64encode(hashlib.sha256(get_settings().jwt_secret.encode()).digest()).decode()
    return Fernet(key.encode())


def encrypt(text: str) -> str:
    return _fernet().encrypt(text.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()


def _sig(payload: str) -> str:
    return hmac.new(get_settings().jwt_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]


def sign_path(path: str, ttl: int = 3600) -> str:
    exp = int(time.time()) + ttl
    return f"{path}?exp={exp}&sig={_sig(f'{path}:{exp}')}"


def verify_signed(path: str, exp: int, sig: str) -> bool:
    return exp >= time.time() and hmac.compare_digest(sig, _sig(f"{path}:{exp}"))


def hash_id(value: str) -> str:
    """Short, non-reversible digest used in audit logs instead of raw student IDs."""
    return hashlib.sha256((get_settings().jwt_secret + value).encode()).hexdigest()[:12]
