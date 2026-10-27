"""Fetch vetted, public MCPS sources and verify their text before indexing.

Run from backend/: .venv/bin/python scripts/sync_public_sources.py
This never fetches Canvas, Synergy, or student records.
"""
import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from app.rag.loaders import load_file

MAX_SOURCE_BYTES = 15 * 1024 * 1024
USER_AGENT = "EsolvPublicSourceSync/1.0 (MCPS public ELD documents)"


def _allowed(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and (parsed.hostname or "").endswith(".montgomeryschoolsmd.org")


def sync() -> list[dict]:
    settings = get_settings()
    registry = json.loads((settings.data_dir / "public_sources.json").read_text())
    docs_dir = settings.docs_dir
    docs_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = docs_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    inventory = []
    seen = set()


    with tempfile.TemporaryDirectory(prefix="esolv-sources-") as staging:
        stage = Path(staging)
        with httpx.Client(follow_redirects=True, timeout=60, headers={"User-Agent": USER_AGENT}) as client:
            for source in registry:
                name, url = source["filename"], source["url"]
                if Path(name).name != name or Path(name).suffix.lower() not in {".html", ".pdf"}:
                    raise ValueError(f"Invalid source filename: {name}")
                if name in seen or not _allowed(url):
                    raise ValueError(f"Duplicate or non-MCPS source: {url}")
                seen.add(name)
                response = client.get(url)
                response.raise_for_status()
                if not _allowed(str(response.url)):
                    raise ValueError(f"Source redirected outside MCPS: {url}")
                data = response.content
                if not data or len(data) > MAX_SOURCE_BYTES:
                    raise ValueError(f"Source is empty or too large: {url}")
                content_type = response.headers.get("content-type", "").lower()
                if name.endswith(".pdf") and (not data.startswith(b"%PDF") or "pdf" not in content_type):
                    raise ValueError(f"Expected a PDF: {url}")
                if name.endswith(".html") and "html" not in content_type:
                    raise ValueError(f"Expected HTML: {url}")
                candidate = stage / name
                candidate.write_bytes(data)
                document = load_file(candidate, source)
                text_chars = sum(len(section.text) for section in document.sections) if document else 0
                if text_chars < 150:
                    raise ValueError(f"Too little extractable text ({text_chars} chars): {url}")
                inventory.append({
                    "filename": name, "url": url, "title": source["title"], "doc_type": source["doc_type"],
                    "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
                    "sections": len(document.sections), "text_chars": text_chars,
                })
                print(f"Verified {name}: {len(document.sections)} sections, {text_chars:,} text chars")

        for item in inventory:
            (stage / item["filename"]).replace(docs_dir / item["filename"])
            manifest[item["filename"]] = {
                "title": item["title"], "url": item["url"], "doc_type": item["doc_type"],
            }
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        report = {"synced_at_utc": datetime.now(timezone.utc).isoformat(), "sources": inventory}
        (settings.data_dir / "public_source_inventory.json").write_text(json.dumps(report, indent=2) + "\n")
    return inventory


if __name__ == "__main__":
    sources = sync()
    print(f"Synced {len(sources)} verified public sources; re-run app.rag.ingest to rebuild Chroma.")
