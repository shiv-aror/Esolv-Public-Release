import time

import jwt

from ..config import get_settings

ALG = "HS256"


def issue_session(email: str, name: str = "", picture: str = "") -> tuple[str, int]:
    s = get_settings()
    exp = int(time.time()) + s.jwt_ttl_minutes * 60
    token = jwt.encode(
        {"sub": email.lower(), "name": name, "picture": picture, "aud": "esolv", "exp": exp},
        s.jwt_secret, algorithm=ALG,
    )
    return token, exp


def verify_session(token: str) -> dict:
    return jwt.decode(token, get_settings().jwt_secret, algorithms=[ALG], audience="esolv")


def issue_state(email: str, purpose: str, ttl: int = 600) -> str:
    return jwt.encode({"sub": email, "aud": purpose, "exp": int(time.time()) + ttl},
                      get_settings().jwt_secret, algorithm=ALG)


def verify_state(token: str, purpose: str) -> str:
    return jwt.decode(token, get_settings().jwt_secret, algorithms=[ALG], audience=purpose)["sub"]
