from datetime import datetime, timedelta, timezone

from app.llm.toolbox import Toolbox


async def test_toolbox_lists_all_tools():
    async with Toolbox("t@mcpsmd.org") as tb:
        names = {t["function"]["name"] for t in tb.openai_tools()}
    assert {"search_mcps_knowledge", "get_document_section", "list_sources", "list_my_courses", "find_student",
            "get_student_profile", "get_accommodations", "list_assignments", "list_upcoming_assignments",
            "get_course_page", "get_demo_student"} <= names


async def test_demo_student_comes_from_synthetic_csv():
    async with Toolbox("t@mcpsmd.org") as tb:
        result = await tb.call("get_demo_student", {"sis_id": "123456"})
    assert result["student"] == {"name": "Maria Santos", "sis_id": "123456"}
    assert "SYNTHETIC DEMO ONLY" in result["chunks"][0]["text"]
    assert "Extended time (1.5x)" in result["chunks"][0]["text"]


async def test_upcoming_assignments_check_all_teaching_courses(monkeypatch):
    from app.mcp import canvas_server
    from app.mcp.context import current_user_email

    now = datetime.now(timezone.utc)
    class Canvas:
        base_url = "https://canvas.example.edu"
        async def my_courses(self):
            return [{"id": 1, "name": "ELD 3"}, {"id": 2, "name": "ELD 5"}, {"id": 3, "name": "No due work"}]
        async def assignments(self, course_id):
            if course_id == 3:
                return [{"name": "Undated", "due_at": None}]
            return [{"name": f"Work {course_id}", "due_at": (now + timedelta(days=course_id)).isoformat(),
                     "html_url": f"{self.base_url}/courses/{course_id}/assignments/{course_id}"},
                    {"name": "Past work", "due_at": (now - timedelta(days=1)).isoformat()}]

    async def client(): return Canvas()
    monkeypatch.setattr(canvas_server, "_client", client)
    monkeypatch.setattr(canvas_server, "audit", lambda *args: None)
    token = current_user_email.set("teacher@mcpsmd.org")
    try:
        result = await canvas_server.list_upcoming_assignments()
    finally:
        current_user_email.reset(token)
    assert result["courses_checked"] == ["ELD 3", "ELD 5", "No due work"]
    assert result["teaching_course_count"] == 3
    assert "teacher teaches 3 Canvas courses" in result["sources"][0]["evidence"]
    assert [a["name"] for a in result["assignments"]] == ["Work 1", "Work 2"]
    assert result["total_found"] == 2
    assert result["sources"][1]["url"].endswith("/assignments/1")


async def test_find_student_and_accommodations():
    async with Toolbox("t@mcpsmd.org") as tb:
        found = await tb.call("find_student", {"query": "123456"})
        assert found["matches"][0]["student"]["name"] == "Maria Santos"
        acc = await tb.call("get_accommodations", {"sis_id": "123456"})
        assert "Extended time (1.5x)" in acc["record"]["accommodations"]
        assert acc["sources"][0]["title"]


async def test_other_teachers_students_are_not_visible():
    async with Toolbox("t@mcpsmd.org") as tb:
        res = await tb.call("get_accommodations", {"sis_id": "999999"})
        assert "not enrolled" in res["error"]
        res = await tb.call("find_student", {"query": "Nobody Here"})
        assert res["matches"] == []
        res = await tb.call("list_assignments", {"course_id": 424242})
        assert "don't teach" in res["error"]


async def test_knowledge_search_tool():
    async with Toolbox("t@mcpsmd.org") as tb:
        res = await tb.call("search_mcps_knowledge", {"query": "accommodations for testing extended time"})
        assert res["chunks"] and res["relevance"] > 0
        docs = await tb.call("list_sources", {})
        assert len(docs["documents"]) >= 8
        assert any(d["title"].startswith("MCPS Policy IOD") for d in docs["documents"])


async def test_tools_require_a_user():
    from app.mcp.context import current_user_email
    tok = current_user_email.set(None)
    try:
        from app.mcp.canvas_server import list_my_courses
        res = await list_my_courses()
        assert "error" in res
    finally:
        current_user_email.reset(tok)


def test_mcp_http_endpoints_require_auth(client, user_token):
    assert client.post("/mcp/knowledge/", json={}).status_code == 401
    hdr = {"Authorization": f"Bearer {user_token}", "Accept": "application/json, text/event-stream"}
    init = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    r = client.post("/mcp/knowledge/", json=init, headers=hdr)
    assert r.status_code == 200 and "search_mcps_knowledge" in r.text
