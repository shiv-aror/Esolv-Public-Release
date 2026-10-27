"""Canvas MCP server. READ-ONLY tools; every student lookup is scoped to courses the signed-in teacher teaches."""
import asyncio
from datetime import datetime, timedelta, timezone

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from ..canvas import tokens
from ..canvas.client import CanvasError
from ..db import audit
from ..providers.accommodations import get_provider
from ..security import hash_id
from .context import require_user

mcp = FastMCP(
    "esolv-canvas",
    instructions="Read-only access to the signed-in teacher's own Canvas courses and enrolled students.",
    stateless_http=True, json_response=True, streamable_http_path="/",
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


def _student_view(s: dict) -> dict:
    return {"name": s["name"], "sortable_name": s.get("sortable_name", ""), "sis_id": s["sis_id"], "canvas_id": s["canvas_id"]}


def _matches(s: dict, q: str) -> bool:
    q = q.strip().lower()
    if not q:
        return False
    login_local = str(s.get("login_id", "")).split("@")[0].lower()
    return q in {s["sis_id"].lower(), login_local, s["name"].lower(), s.get("sortable_name", "").lower()} or (len(q) >= 3 and q in s["name"].lower())


async def _find(client, query: str, course_id: int | None = None) -> list[dict]:
    """Search only inside the teacher's own courses. Matching is done here (exact student ID / login, or part of the name)
    so it doesn't depend on how a given Canvas instance interprets search_term."""
    courses = await client.my_courses()
    if course_id is not None:
        courses = [c for c in courses if int(c["id"]) == int(course_id)]
    found = []
    for c in courses:
        for s in await client.course_students(c["id"]):
            if _matches(s, query):
                found.append({"student": _student_view(s), "course": {"id": c["id"], "name": c["name"]}})
    return found


async def _client():
    return await tokens.get_client(require_user())


def _err(e: Exception) -> dict:
    return {"error": str(e) if isinstance(e, (CanvasError, tokens.NotConnected, PermissionError)) else "Canvas request failed"}


@mcp.tool()
async def list_my_courses() -> dict:
    """List the active Canvas courses the signed-in teacher teaches."""
    try:
        email = require_user()
        client = await _client()
        courses = await client.my_courses()
        audit(email, "tool.list_my_courses")
        return {"courses": courses, "sources": [{"ref": "c", "title": "Canvas: my courses", "url": client.base_url + "/courses"}]}
    except Exception as e:
        return _err(e)


@mcp.tool()
async def find_student(query: str, course_id: int | None = None) -> dict:
    """Find a student in the teacher's own courses by SIS/student ID or name. Returns only students enrolled with this teacher."""
    try:
        email = require_user()
        client = await _client()
        matches = await _find(client, query, course_id)
        audit(email, "tool.find_student", f"q={hash_id(query)} n={len(matches)}")
        if not matches:
            return {"matches": [], "note": "No student with that ID or name is enrolled in any of your Canvas courses."}
        return {"matches": matches}
    except Exception as e:
        return _err(e)


@mcp.tool()
async def get_student_profile(sis_id: str) -> dict:
    """Basic roster profile for one student (name, courses). Only for students in the teacher's courses."""
    try:
        email = require_user()
        client = await _client()
        matches = [m for m in await _find(client, sis_id) if m["student"]["sis_id"] == sis_id]
        audit(email, "tool.get_student_profile", f"s={hash_id(sis_id)} n={len(matches)}")
        if not matches:
            return {"error": "That student is not enrolled in any of your Canvas courses."}
        return {"student": matches[0]["student"], "courses": [m["course"] for m in matches],
                "sources": [{"ref": "c", "title": f"Canvas roster: {matches[0]['course']['name']}",
                             "url": f"{client.base_url}/courses/{matches[0]['course']['id']}/users"}]}
    except Exception as e:
        return _err(e)


@mcp.tool()
async def get_accommodations(sis_id: str) -> dict:
    """Look up recorded ELD accommodations for one student. The student must be enrolled in one of the teacher's courses."""
    try:
        email = require_user()
        client = await _client()
        matches = [m for m in await _find(client, sis_id) if m["student"]["sis_id"] == sis_id]
        audit(email, "tool.get_accommodations", f"s={hash_id(sis_id)} n={len(matches)}")
        if not matches:
            return {"error": "That student is not enrolled in any of your Canvas courses, so I can't look up their accommodations."}
        m = matches[0]
        rec = await get_provider().get(m["student"], m["course"]["id"], client)
        if rec is None:
            return {"student": m["student"], "record": None,
                    "note": "No accommodations record was found for this student in the configured source."}
        src = rec.pop("source")
        return {"student": m["student"], "course": m["course"], "record": rec, "sources": [{"ref": "a", **src}]}
    except Exception as e:
        return _err(e)


@mcp.tool()
async def list_assignments(course_id: int) -> dict:
    """List assignments (name, due date, points, link) for one of the teacher's courses."""
    try:
        email = require_user()
        client = await _client()
        if int(course_id) not in {int(c["id"]) for c in await client.my_courses()}:
            return {"error": "You don't teach that course."}
        audit(email, "tool.list_assignments", f"course={course_id}")
        items = await client.assignments(course_id)
        return {"assignments": items, "sources": [{"ref": "c", "title": "Canvas assignments", "url": f"{client.base_url}/courses/{course_id}/assignments"}]}
    except Exception as e:
        return _err(e)


@mcp.tool()
async def list_upcoming_assignments(days_ahead: int = 30) -> dict:
    """Find assignments due in the next 30 days across every Canvas course the signed-in teacher teaches."""
    try:
        email = require_user()
        client = await _client()
        courses = await client.my_courses()
        days = max(1, min(days_ahead, 90))
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=days)
        limit = asyncio.Semaphore(4)

        async def read_course(course: dict) -> tuple[dict, list[dict] | None]:
            try:
                async with limit:
                    return course, await client.assignments(course["id"])
            except Exception:
                return course, None

        found, failed = [], []
        for course, assignments in await asyncio.gather(*(read_course(c) for c in courses)):
            if assignments is None:
                failed.append(course["name"])
                continue
            for item in assignments:
                due = item.get("due_at")
                if not due:
                    continue
                try:
                    when = datetime.fromisoformat(due.replace("Z", "+00:00"))
                    if when.tzinfo is None:
                        continue
                    when = when.astimezone(timezone.utc)
                except (TypeError, ValueError):
                    continue
                if now <= when <= end:
                    found.append((when, {"course": course["name"], "course_id": course["id"],
                                         "name": item["name"], "due_at": due, "url": item.get("html_url", "")}))
        found.sort(key=lambda pair: pair[0])
        shown = [item for _, item in found[:20]]
        audit(email, "tool.list_upcoming_assignments", f"courses={len(courses)} found={len(found)}")
        return {"courses_checked": [c["name"] for c in courses], "teaching_course_count": len(courses),
                "from_utc": now.isoformat(),
                "through_utc": end.isoformat(), "assignments": shown, "total_found": len(found),
                "omitted_count": len(found) - len(shown), "courses_failed": failed,
                "sources": [{"ref": "courses", "title": "Canvas: courses you teach", "url": client.base_url + "/courses",
                             "evidence": f"The signed-in teacher teaches {len(courses)} Canvas courses: {', '.join(c['name'] for c in courses) or 'none'}."}]
                + [{"ref": str(i), "title": f"Canvas assignment: {a['name']} — {a['course']}", "url": a["url"],
                    "evidence": f"{a['name']} in {a['course']} is due {a['due_at']}."} for i, a in enumerate(shown)]}
    except Exception as e:
        return _err(e)


@mcp.tool()
async def get_course_page(course_id: int, page_url: str = "") -> dict:
    """Read a Canvas course page by its URL slug; with no page_url, list the course's pages."""
    try:
        email = require_user()
        client = await _client()
        if int(course_id) not in {int(c["id"]) for c in await client.my_courses()}:
            return {"error": "You don't teach that course."}
        audit(email, "tool.get_course_page", f"course={course_id}")
        if not page_url:
            return {"pages": await client.pages(course_id)}
        p = await client.page(course_id, page_url)
        return {"page": p, "sources": [{"ref": "p", "title": f"Canvas page: {p['title']}", "url": p["html_url"]}]}
    except Exception as e:
        return _err(e)
