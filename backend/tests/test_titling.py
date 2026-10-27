import pytest

from app.llm.titling import clean_title, generate_title


class FakeLLM:
    def __init__(self):
        self.messages = None

    async def chat(self, messages, **kwargs):
        self.messages = messages
        return {"content": '"Documented ELD Accommodations"\nAnything else'}


def test_clean_title_rejects_extra_lines_and_long_titles():
    assert clean_title('"Documented ELD Accommodations"\nAnything else') == "Documented ELD Accommodations"
    assert len(clean_title("very " * 30)) <= 60
    assert clean_title("Accommodations for Student ABCD") == "Accommodations for student"


@pytest.mark.asyncio
async def test_title_masks_student_id_before_model_call():
    llm = FakeLLM()
    title = await generate_title("teacher@mcpsmd.org", "What accommodations does 123456 have?", llm)
    assert title == "Documented ELD Accommodations"
    assert "123456" not in str(llm.messages)


def test_title_route_requires_auth_and_returns_generated_title(client, user_token, monkeypatch):
    from app.routes import chat

    async def fake(_email, _question):
        return "ELD placement guidance"

    monkeypatch.setattr(chat, "generate_title", fake)
    assert client.post("/chat/title", json={"question": "ELD placement?"}).status_code == 401
    r = client.post("/chat/title", json={"question": "ELD placement?"},
                    headers={"Authorization": f"Bearer {user_token}"})
    assert r.status_code == 200
    assert r.json() == {"title": "ELD placement guidance"}
