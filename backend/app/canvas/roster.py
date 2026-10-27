"""Short-lived roster cache so every student name/ID the teacher could mention can be masked before text leaves the server."""
import time

from . import tokens

_TTL = 600
_cache: dict[str, tuple[float, list[dict]]] = {}


async def get_roster(email: str) -> list[dict]:
    hit = _cache.get(email)
    if hit and time.monotonic() - hit[0] < _TTL:
        return hit[1]
    students: list[dict] = []
    try:
        client = await tokens.get_client(email)
        try:
            for c in (await client.my_courses())[:15]:
                students.extend(await client.course_students(c["id"]))
        finally:
            await client.aclose()
    except Exception:
        students = []
    _cache[email] = (time.monotonic(), students)
    return students


def clear(email: str | None = None) -> None:
    if email:
        _cache.pop(email, None)
    else:
        _cache.clear()
