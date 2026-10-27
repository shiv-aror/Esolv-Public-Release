import io

import pytest
from docx import Document

from app.guardrails import files as fg


def _docx(text="Heading text\n"):
    d = Document(); d.add_paragraph(text * 3)
    b = io.BytesIO(); d.save(b); return b.getvalue()


def test_extract_txt_md_csv_docx():
    assert fg.extract("a.txt", b"ELD plan notes for review")["text"].startswith("ELD plan")
    assert "x,y" in fg.extract("a.csv", b"x,y\n1,2\n")["text"]
    out = fg.extract("plan.docx", _docx("Accommodations: extended time. "))
    assert "extended time" in out["text"] and out["name"] == "plan.docx"


def test_rejects_bad_files():
    for name, raw in [("a.exe", b"MZ..."), ("a.pdf", b"not a pdf at all"), ("a.docx", b"plain text"), ("a.txt", b""), ("a.txt", b"  ")]:
        with pytest.raises(fg.FileRejected):
            fg.extract(name, raw)
    with pytest.raises(fg.FileRejected):
        fg.extract("a.txt", b"x" * (11 * 1024 * 1024))


def test_truncates_long_text():
    out = fg.extract("big.txt", b"word " * 20000)
    assert out["truncated"] and len(out["text"]) <= 24000 and out["chars"] > 24000


def test_upload_route_and_chat_limits(client, user_token):
    h = {"Authorization": f"Bearer {user_token}"}
    r = client.post("/uploads/file", files={"file": ("notes.txt", b"ELD review is due in March.", "text/plain")}, headers=h)
    assert r.status_code == 200 and r.json()["name"] == "notes.txt" and "March" in r.json()["text"]
    assert client.post("/uploads/file", files={"file": ("x.exe", b"MZxx", "application/octet-stream")}, headers=h).status_code == 400
    assert client.post("/uploads/file", files={"file": ("n.txt", b"hello there friend", "text/plain")}).status_code == 401
    too_many = {"messages": [{"role": "user", "content": "hi there"}], "files": [{"name": f"{i}.txt", "text": "abc def"} for i in range(5)]}
    assert client.post("/chat", json=too_many, headers=h).status_code == 400
