from app.rag import retriever
from app.mcp.knowledge_server import include_policy_continuations
from app.rag.chunking import MAX_CHARS, chunk_document
from app.rag.models import Document, Section


def test_chunking_respects_sections_and_size():
    long = "\n\n".join(f"Paragraph {i}. " + "word " * 200 for i in range(10))
    doc = Document("d1", "T", "", sections=[Section("A > B", long), Section("C", "short but long enough to keep " * 3)])
    chunks = chunk_document(doc)
    assert all(len(c.text) <= MAX_CHARS + 500 for c in chunks)
    assert {c.section for c in chunks} == {"A > B", "C"}
    assert len([c for c in chunks if c.section == "A > B"]) > 1


def test_retriever_finds_right_document():
    r = retriever.search("IOD-RA accommodations on final examinations")
    assert r and "IOD-RA" in r[0].title
    assert r[0].url.endswith("/iodra.pdf") and r[0].page == 2
    r = retriever.search("high school ELD credits and seminars")
    assert r and "high school ELD instruction" in r[0].title
    assert r[0].url.endswith("/curriculum/eld/high/")


def test_retriever_finds_official_accommodations_form():
    results = retriever.search("MCPS Form 320-53 testing accommodations and accessibility features")
    assert results[0].filename == "mcps-form-320-53.pdf"
    assert results[0].url.endswith("/departments/forms/pdf/320-53.pdf")


def test_policy_search_includes_page_after_a_split_accommodations_rule():
    query = "What accommodations should ESOL students receive during non-ESOL instruction and assessments?"
    chunks = include_policy_continuations(retriever.search(query))
    pages = [c.page for c in chunks if c.filename == "mcps-regulation-iod-ra.pdf"]
    assert pages[:2] == [2, 3]
    continuation = next(c for c in chunks if c.filename == "mcps-regulation-iod-ra.pdf" and c.page == 3)
    assert "linguistically modified content" in continuation.text


def test_retriever_doc_type_filter_and_irrelevance():
    assert retriever.search("accommodations", doc_type="nonexistent") == []
    assert retriever.best_relevance(retriever.search("capital of France")) < 0.2
