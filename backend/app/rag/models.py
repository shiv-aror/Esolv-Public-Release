from dataclasses import dataclass, field


@dataclass
class Section:
    """A contiguous piece of a source document (heading path + text + page)."""
    heading: str
    text: str
    page: int | None = None


@dataclass
class Document:
    doc_id: str
    title: str
    url: str
    doc_type: str = "guidance"
    filename: str = ""
    sections: list[Section] = field(default_factory=list)


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    text: str
    title: str
    section: str
    page: int | None
    url: str
    doc_type: str
    filename: str = ""
    score: float = 0.0


def to_meta(c: Chunk) -> dict:
    return {
        "doc_id": c.doc_id, "title": c.title, "section": c.section, "page": c.page if c.page is not None else -1,
        "url": c.url, "doc_type": c.doc_type, "filename": c.filename,
    }
