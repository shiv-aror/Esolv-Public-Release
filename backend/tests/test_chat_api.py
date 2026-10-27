import base64
import io
import json

from PIL import Image

from app.llm import orchestrator


def parse_sse(text):
    events = []
    for block in text.strip().split("\n\n"):
        ev = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        events.append((ev["event"], json.loads(ev["data"])))
    return events


def png_url():
    buf = io.BytesIO(); Image.new("RGB", (20, 20), "blue").save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def test_chat_requires_auth(client):
    assert client.post("/chat", json={"messages": [{"role": "user", "content": "hi"}]}).status_code == 401


def test_chat_streams_status_delta_done(client, user_token, monkeypatch):
    async def fake(email, msgs, ctx, images, emit, **kw):
        await emit({"type": "status", "text": "Searching MCPS materials…"})
        await emit({"type": "sources", "text": "Sources used for fact checking", "stage": "checking", "sources": [{"title": "IOD-RA", "url": "https://ww2.montgomeryschoolsmd.org/departments/policy/pdf/iodra.pdf#page=2"}]})
        return {"answer": "Hello " * 30, "citations": [], "verification": {"status": "verified", "notes": []}, "flags": []}

    monkeypatch.setattr(orchestrator, "run_chat", fake)
    r = client.post("/chat", json={"messages": [{"role": "user", "content": "x"}]}, headers={"Authorization": f"Bearer {user_token}"})
    kinds = [k for k, _ in parse_sse(r.text)]
    assert kinds[0] == "status" and "sources" in kinds and "delta" in kinds and kinds[-1] == "done"
    assert next(d for k, d in parse_sse(r.text) if k == "sources")["sources"][0]["url"].endswith("iodra.pdf#page=2")
    assert "".join(d["text"] for k, d in parse_sse(r.text) if k == "delta") == "Hello " * 30


def test_chat_validation(client, user_token, monkeypatch):
    h = {"Authorization": f"Bearer {user_token}"}
    assert client.post("/chat", json={"messages": [{"role": "assistant", "content": "x"}]}, headers=h).status_code == 400
    assert client.post("/chat", json={"messages": [{"role": "user", "content": "x"}], "images": ["data:image/gif;base64,AAAA"]}, headers=h).status_code == 400
    assert client.post("/chat", json={"messages": [{"role": "user", "content": "x"}], "images": [png_url()] * 9}, headers=h).status_code == 400
    assert client.post("/chat", json={"messages": [{"role": "user", "content": "x" * 7000}]}, headers=h).status_code == 413


def test_chat_errors_do_not_leak(client, user_token, monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("secret student 123456 details")

    monkeypatch.setattr(orchestrator, "run_chat", boom)
    r = client.post("/chat", json={"messages": [{"role": "user", "content": "x"}]}, headers={"Authorization": f"Bearer {user_token}"})
    assert "123456" not in r.text and "error" in r.text


def test_chat_reports_model_key_limit(client, user_token, monkeypatch):
    from app.llm.openrouter import LLMQuotaError

    async def limited(*a, **k):
        raise LLMQuotaError("OpenRouter API key limit exceeded.")

    monkeypatch.setattr(orchestrator, "run_chat", limited)
    r = client.post("/chat", json={"messages": [{"role": "user", "content": "x"}]},
                    headers={"Authorization": f"Bearer {user_token}"})
    error = next(data for event, data in parse_sse(r.text) if event == "error")
    assert "spending limit" in error["message"]


def test_image_upload_and_feedback(client, user_token):
    h = {"Authorization": f"Bearer {user_token}"}
    buf = io.BytesIO(); Image.new("RGB", (10, 10)).save(buf, "PNG")
    r = client.post("/uploads/image", files={"file": ("a.png", buf.getvalue(), "image/png")}, headers=h)
    assert r.status_code == 200 and r.json()["data_url"].startswith("data:image/")
    assert client.post("/uploads/image", files={"file": ("a.png", b"junk", "image/png")}, headers=h).status_code == 400
    assert client.post("/feedback", json={"rating": "up"}, headers=h).json() == {"ok": True}
    assert client.post("/feedback", json={"rating": "meh"}, headers=h).status_code == 422


def test_signed_source_links(client):
    from app.security import sign_path
    ok = client.get(sign_path("/sources/file/eld-accommodations-guide.md"))
    assert ok.status_code == 200 and "Accommodation" in ok.text
    assert client.get("/sources/file/eld-accommodations-guide.md?exp=9999999999&sig=bad").status_code == 403
    assert client.get(sign_path("/sources/file/..%2F..%2F.env")).status_code in (403, 404)


def test_rate_limit(client, user_token, monkeypatch):
    from app.routes import chat as chat_route
    monkeypatch.setattr(chat_route, "_limiter", chat_route.RateLimiter(2))
    monkeypatch.setattr(orchestrator, "run_chat", lambda *a, **k: _ok())
    h = {"Authorization": f"Bearer {user_token}"}
    codes = [client.post("/chat", json={"messages": [{"role": "user", "content": "x"}]}, headers=h).status_code for _ in range(4)]
    assert codes[:2] == [200, 200] and 429 in codes[2:]


async def _ok():
    return {"answer": "ok", "citations": [], "verification": {"status": "verified", "notes": []}, "flags": []}
