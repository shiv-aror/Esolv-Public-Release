from app.providers.accommodations.csv_provider import CsvAccommodations
from app.canvas.mock import MockCanvasClient


async def test_synthetic_records_only_with_mock_canvas(tmp_path):
    (tmp_path / "accommodations.sample.csv").write_text(
        "sis_id,eld_level,accommodations\n123456,3,Demo glossary\n"
    )
    provider = CsvAccommodations()
    provider.data_dir = tmp_path
    student = {"sis_id": "123456"}
    assert (await provider.get(student, 1, MockCanvasClient()))["accommodations"] == ["Demo glossary"]
    assert await provider.get(student, 1, object()) is None
