from ...config import get_settings


class CanvasColumnAccommodations:
    """Reads a Canvas custom gradebook column (default title 'Accommodations') for the student."""
    name = "canvas_column"

    async def get(self, student: dict, course_id: int, client) -> dict | None:
        title = get_settings().canvas_accommodations_column.lower()
        cols = await client.custom_columns(course_id)
        col = next((c for c in cols if c.get("title", "").lower() == title), None)
        if not col:
            return None
        for row in await client.custom_column_data(course_id, col["id"]):
            if int(row.get("user_id", -1)) == int(student["canvas_id"]) and row.get("content"):
                return {
                    "eld_level": None,
                    "accommodations": [a.strip() for a in str(row["content"]).replace("\n", ";").split(";") if a.strip()],
                    "plan_review_date": None,
                    "notes": "",
                    "source": {"title": f"Canvas gradebook column “{col['title']}”",
                               "url": f"{client.base_url}/courses/{course_id}/gradebook"},
                }
        return None
