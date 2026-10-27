"""Read-only async Canvas LMS REST client (pagination, rate-limit backoff). No write methods exist by design."""
import asyncio
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from ..config import get_settings


class CanvasError(Exception):
    pass


class CanvasAuthError(CanvasError):
    pass


def student_id_of(u: dict, field: str = "auto") -> str:
    """The district student ID (e.g. 123456). Canvas can keep it in sis_user_id, or only in the login (123456@mcpsmd.net)."""
    login_local = str(u.get("login_id") or "").split("@")[0]
    candidates = {
        "sis_user_id": str(u.get("sis_user_id") or ""),
        "login_id": login_local,
        "integration_id": str(u.get("integration_id") or ""),
    }
    if field in candidates:
        return candidates[field]
    return candidates["sis_user_id"] or (login_local if login_local.isdigit() else "") or candidates["integration_id"]


def html_to_text(html: str | None, limit: int = 4000) -> str:
    if not html:
        return ""
    text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
    return text[:limit]


class CanvasClient:
    def __init__(self, base_url: str, token: str, transport: httpx.AsyncBaseTransport | None = None):
        self.base_url = base_url.rstrip("/")
        self._http = httpx.AsyncClient(
            base_url=self.base_url, headers={"Authorization": f"Bearer {token}"}, timeout=30,
            transport=transport, follow_redirects=False,
        )

    async def aclose(self):
        await self._http.aclose()

    async def _get(self, path: str, params: Any = None) -> httpx.Response:
        for attempt in range(4):
            r = await self._http.get(path, params=params)
            if r.status_code == 401:
                raise CanvasAuthError("Canvas rejected the access token (expired or revoked).")
            throttled = r.status_code == 429 or (r.status_code == 403 and "rate limit" in r.text.lower())
            if throttled and attempt < 3:
                await asyncio.sleep(0.5 * 2**attempt)
                continue
            if r.status_code >= 400:
                raise CanvasError(f"Canvas error {r.status_code} on {path}")
            return r
        raise CanvasError("Canvas rate limit exceeded")

    async def _paged(self, path: str, params: Any = None, max_items: int = 500) -> list[dict]:
        items: list[dict] = []
        params = params if params is not None else {}
        r = await self._get(path, {"per_page": 100, **params} if isinstance(params, dict) else params)
        while True:
            data = r.json()
            items.extend(data if isinstance(data, list) else [data])
            nxt = re.search(r'<([^>]+)>;\s*rel="next"', r.headers.get("link", ""))
            if not nxt or len(items) >= max_items:
                break
            url = nxt.group(1).replace(self.base_url, "")
            r = await self._get(url)
        return items[:max_items]


    async def whoami(self) -> dict:
        return (await self._get("/api/v1/users/self")).json()

    async def my_courses(self) -> list[dict]:
        courses = await self._paged("/api/v1/courses", {"enrollment_type": "teacher", "state[]": "available", "include[]": "term"})
        return [
            {"id": c["id"], "name": c.get("name", ""), "code": c.get("course_code", ""),
             "term": (c.get("term") or {}).get("name", ""), "html_url": f"{self.base_url}/courses/{c['id']}"}
            for c in courses if c.get("name")
        ]


    async def course_students(self, course_id: int, search: str | None = None) -> list[dict]:
        params: dict[str, Any] = {"enrollment_type[]": "student", "enrollment_state[]": "active"}
        if search:
            params["search_term"] = search
        users = await self._paged(f"/api/v1/courses/{course_id}/users", params)
        return [
            {"canvas_id": u["id"], "name": u.get("name", ""), "sortable_name": u.get("sortable_name", ""),
             "sis_id": student_id_of(u, get_settings().canvas_student_id_field), "login_id": u.get("login_id", "")}
            for u in users
        ]


    async def assignments(self, course_id: int) -> list[dict]:
        a = await self._paged(f"/api/v1/courses/{course_id}/assignments", {"order_by": "due_at"}, max_items=100)
        return [
            {"id": x["id"], "name": x.get("name", ""), "due_at": x.get("due_at"), "points": x.get("points_possible"),
             "html_url": x.get("html_url", ""), "description": html_to_text(x.get("description"), 800)}
            for x in a
        ]

    async def pages(self, course_id: int) -> list[dict]:
        p = await self._paged(f"/api/v1/courses/{course_id}/pages", {"sort": "title"}, max_items=100)
        return [{"url": x["url"], "title": x.get("title", ""), "html_url": x.get("html_url", "")} for x in p]

    async def page(self, course_id: int, page_url: str) -> dict:
        x = (await self._get(f"/api/v1/courses/{course_id}/pages/{page_url}")).json()
        return {"title": x.get("title", ""), "body": html_to_text(x.get("body"), 6000), "html_url": x.get("html_url", "")}


    async def custom_columns(self, course_id: int) -> list[dict]:
        return await self._paged(f"/api/v1/courses/{course_id}/custom_gradebook_columns")

    async def custom_column_data(self, course_id: int, column_id: int) -> list[dict]:
        return await self._paged(f"/api/v1/courses/{course_id}/custom_gradebook_columns/{column_id}/data")
