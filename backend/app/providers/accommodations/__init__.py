from ...config import get_settings
from .base import AccommodationsProvider
from .canvas_column import CanvasColumnAccommodations
from .csv_provider import CsvAccommodations


def get_provider() -> AccommodationsProvider:
    return CanvasColumnAccommodations() if get_settings().accommodations_provider == "canvas_column" else CsvAccommodations()
