import csv
from pathlib import Path

from ...config import get_settings
from ...canvas.mock import MockCanvasClient


class CsvAccommodations:
    """Reads data/accommodations.csv. Synthetic records are available only in Canvas mock mode."""
    name = "csv"

    def __init__(self, path: Path | None = None):
        d = get_settings().data_dir
        self.path = path
        self.data_dir = d

    async def get(self, student: dict, course_id: int, client) -> dict | None:
        path = self.path or self.data_dir / ("accommodations.sample.csv" if isinstance(client, MockCanvasClient) else "accommodations.csv")
        if not path.exists():
            return None
        with path.open(newline="") as f:
            for row in csv.DictReader(f):
                if row["sis_id"].strip() == student["sis_id"]:
                    return {
                        "eld_level": row.get("eld_level") or None,
                        "accommodations": [a.strip() for a in row.get("accommodations", "").split(";") if a.strip()],
                        "plan_review_date": row.get("plan_review_date") or None,
                        "notes": row.get("notes", ""),
                        "source": {"title": f"{'SYNTHETIC DEMO: ' if path.name.endswith('.sample.csv') else ''}ELD accommodations record ({path.name})", "url": ""},
                    }
        return None
