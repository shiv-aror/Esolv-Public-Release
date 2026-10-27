import hashlib
import json
from pathlib import Path

from app.config import get_settings
from app.guardrails.pii import Pseudonymizer
from app.llm.orchestrator import Source, _citation
from app.rag.loaders import load_all


def test_public_snapshots_match_verified_inventory():
    data = get_settings().data_dir
    registry = json.loads((data / "public_sources.json").read_text())
    inventory = json.loads((data / "public_source_inventory.json").read_text())["sources"]
    assert len(registry) == len(inventory) >= 9
    assert len({s["url"] for s in registry}) == len(registry)
    for source, verified in zip(registry, inventory):
        assert source["url"] == verified["url"]
        assert source["url"].startswith("https://")
        assert source["url"] != "https://www.montgomeryschoolsmd.org/"
        path = data / "docs" / source["filename"]
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == verified["sha256"]
        assert verified["text_chars"] >= 150


def test_manifest_can_exclude_placeholder_and_summary_files(tmp_path: Path):
    (tmp_path / "manifest.json").write_text(json.dumps({
        "placeholder.md": {"index": False, "url": "https://www.montgomeryschoolsmd.org/"},
        "real.md": {"url": "https://www.montgomeryschoolsmd.org/curriculum/eld/", "title": "Real"},
    }))
    (tmp_path / "placeholder.md").write_text("# Placeholder\n" + "example " * 30)
    (tmp_path / "real.md").write_text("# Real\n" + "official source text " * 30)
    docs = load_all(tmp_path)
    assert len(docs) == 1
    assert docs[0].url == "https://www.montgomeryschoolsmd.org/curriculum/eld/"


def test_pdf_citation_opens_the_retrieved_page():
    pseudo = Pseudonymizer("teacher@mcpsmd.org")
    pdf = Source(id="S1", title="Policy IOD", kind="knowledge", page=4,
                 url="https://ww2.montgomeryschoolsmd.org/departments/policy/pdf/iod%20master.pdf")
    assert _citation(pdf, pseudo)["url"].endswith("iod%20master.pdf#page=4")
    page = Source(id="S2", title="ELD high school", kind="knowledge", page=None,
                  url="https://www.montgomeryschoolsmd.org/curriculum/eld/high/")
    assert _citation(page, pseudo)["url"] == page.url
