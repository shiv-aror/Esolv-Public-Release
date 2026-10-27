from typing import Protocol


class AccommodationsProvider(Protocol):
    """Pluggable source of ELD accommodation records. Returns None when no record exists."""

    name: str

    async def get(self, student: dict, course_id: int, client) -> dict | None: ...
