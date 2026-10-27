"""Student-data pseudonymization.

Nothing that identifies a student (name, student ID) is sent to the LLM provider. Real values are swapped for stable
pseudonyms ("Student K7QF" / "ID-K7QF") derived with an HMAC of the teacher + student, so the same student keeps the same
pseudonym across turns without any server-side state. The teacher's browser receives the answer with real values restored.
"""
import base64
import hashlib
import hmac
import re
from typing import Any

from ..config import get_settings

_ID_RE = re.compile(r"(?<![\w-])\d{6,9}(?![\w-])")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_TOKEN_RE = re.compile(r"\b(Student|ID-)\s?([A-Z2-7]{4})\b")
_STUDENT_KEYS = ("name", "sortable_name", "short_name", "sis_id", "login_id")


class Pseudonymizer:
    def __init__(self, user_email: str):
        self.user = user_email.lower()
        self._to_token: dict[str, str] = {}
        self._from_token: dict[str, str] = {}
        self._regex: re.Pattern | None = None


    def _code(self, key: str) -> str:
        d = hmac.new(get_settings().jwt_secret.encode(), f"{self.user}|{key}".encode(), hashlib.sha256).digest()
        return base64.b32encode(d)[:4].decode()

    def _add(self, real: str, token: str, display: str | None = None) -> None:
        real = real.strip()
        if not real:
            return
        self._to_token[real.lower()] = token
        self._from_token.setdefault(token, display or real)
        self._regex = None

    def _rebuild(self) -> re.Pattern | None:
        if not self._to_token:
            return None
        alts = sorted((re.escape(k) for k in self._to_token), key=len, reverse=True)
        self._regex = re.compile(r"(?<![\w-])(" + "|".join(alts) + r")(?![\w])", re.IGNORECASE)
        return self._regex


    def register_student(self, name: str = "", sortable: str = "", sis_id: str = "", login: str = "") -> None:
        code = self._code(sis_id or name or login)
        stu, idt = f"Student {code}", f"ID-{code}"
        full = name or sortable
        if full:
            self._from_token[stu] = full
        for variant in {name, sortable}:
            if variant:
                self._add(variant, stu, full)
        parts = [p for p in re.split(r"[\s,]+", full) if len(p) >= 4]
        for p in parts:
            if p.lower() not in self._to_token:
                self._add(p, stu, full)
        if sis_id:
            self._add(sis_id, idt, sis_id)
        if login and len(login) >= 4:
            self._add(login, idt, sis_id or login)

    def register_roster(self, students: list[dict]) -> None:

        counts: dict[str, int] = {}
        for s in students:
            for p in re.split(r"[\s,]+", s.get("name", "")):
                counts[p.lower()] = counts.get(p.lower(), 0) + 1
        for s in students:
            self.register_student(s.get("name", ""), s.get("sortable_name", ""), s.get("sis_id", ""), s.get("login_id", ""))
        for tok, n in counts.items():
            if n > 1 and tok in self._to_token:
                del self._to_token[tok]
                self._regex = None

    def register_from_obj(self, obj: Any) -> None:
        """Discover students inside a tool result: any dict that has a 'sis_id'."""
        if isinstance(obj, dict):
            if "sis_id" in obj and isinstance(obj.get("sis_id"), str) and obj["sis_id"]:
                self.register_student(obj.get("name", ""), obj.get("sortable_name", ""), obj["sis_id"], obj.get("login_id", ""))
            for v in obj.values():
                self.register_from_obj(v)
        elif isinstance(obj, list):
            for v in obj:
                self.register_from_obj(v)


    def mask(self, text: str) -> str:
        if not text:
            return text
        text = _SSN_RE.sub("[SSN]", text)

        for m in set(_ID_RE.findall(text)):
            if m.lower() not in self._to_token:
                code = self._code(m)
                self._add(m, f"ID-{code}", m)
                self._from_token.setdefault(f"Student {code}", m)
        rx = self._regex or self._rebuild()
        if rx:
            text = rx.sub(lambda m: self._to_token[m.group(1).lower()], text)
        return text

    def mask_obj(self, obj: Any) -> Any:
        if isinstance(obj, str):
            return self.mask(obj)
        if isinstance(obj, dict):
            return {k: self.mask_obj(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self.mask_obj(v) for v in obj]
        return obj

    def unmask(self, text: str) -> str:
        def sub(m: re.Match) -> str:
            tok = f"{'Student ' if m.group(1) == 'Student' else 'ID-'}{m.group(2)}"
            return self._from_token.get(tok, m.group(0))
        return _TOKEN_RE.sub(sub, text or "")

    def unmask_obj(self, obj: Any) -> Any:
        if isinstance(obj, str):
            return self.unmask(obj)
        if isinstance(obj, dict):
            return {k: self.unmask_obj(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self.unmask_obj(v) for v in obj]
        return obj

    def has_tokens(self) -> bool:
        return bool(self._from_token)
