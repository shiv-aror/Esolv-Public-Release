import httpx
import pytest
import respx

from app.canvas.client import CanvasAuthError, CanvasClient, CanvasError

BASE = "https://canvas.test"


@respx.mock
async def test_pagination_and_students():
    respx.get(f"{BASE}/api/v1/courses/1/users", params={"page": "2"}).mock(
        return_value=httpx.Response(200, json=[{"id": 2, "name": "B B", "sortable_name": "B, B", "sis_user_id": "222", "login_id": "bb"}]))
    respx.get(f"{BASE}/api/v1/courses/1/users").mock(return_value=httpx.Response(
        200, json=[{"id": 1, "name": "A A", "sortable_name": "A, A", "sis_user_id": "111", "login_id": "aa"}],
        headers={"link": f'<{BASE}/api/v1/courses/1/users?page=2>; rel="next"'}))
    c = CanvasClient(BASE, "tok")
    studs = await c.course_students(1)
    assert [s["sis_id"] for s in studs] == ["111", "222"]
    await c.aclose()


@respx.mock
async def test_auth_error_and_http_error():
    respx.get(f"{BASE}/api/v1/users/self").mock(return_value=httpx.Response(401, json={}))
    respx.get(f"{BASE}/api/v1/courses").mock(return_value=httpx.Response(500, text="boom"))
    c = CanvasClient(BASE, "bad")
    with pytest.raises(CanvasAuthError):
        await c.whoami()
    with pytest.raises(CanvasError):
        await c.my_courses()


@respx.mock
async def test_rate_limit_backoff(monkeypatch):
    async def nosleep(_): ...
    monkeypatch.setattr("app.canvas.client.asyncio.sleep", nosleep)
    route = respx.get(f"{BASE}/api/v1/users/self").mock(side_effect=[
        httpx.Response(403, text="403 Forbidden (Rate Limit Exceeded)"), httpx.Response(200, json={"id": 9, "name": "T"})])
    c = CanvasClient(BASE, "t")
    assert (await c.whoami())["id"] == 9 and route.call_count == 2


@respx.mock
async def test_only_get_requests_are_ever_made():
    route = respx.route().mock(return_value=httpx.Response(200, json=[]))
    c = CanvasClient(BASE, "t")
    await c.my_courses(); await c.assignments(1); await c.pages(1)
    assert {call.request.method for call in route.calls} == {"GET"}


def test_pat_endpoint_validates_and_stores(client, user_token):
    h = {"Authorization": f"Bearer {user_token}"}
    with respx.mock:
        respx.get("https://mcpsmd.instructure.com/api/v1/users/self").mock(return_value=httpx.Response(200, json={"id": 5, "name": "Ms. T"}))
        r = client.post("/canvas/token", json={"token": "1234~abcdefghijklmnop"}, headers=h)
    assert r.status_code == 200 and r.json()["canvas_name"] == "Ms. T"
    st = client.get("/canvas/status", headers=h).json()
    assert st["connected"] and st["kind"] == "pat"
    assert client.delete("/canvas/token", headers=h).json()["connected"] is False
    assert client.get("/canvas/status", headers=h).json()["kind"] == "mock"


def test_bad_pat_rejected(client, user_token):
    with respx.mock:
        respx.get("https://mcpsmd.instructure.com/api/v1/users/self").mock(return_value=httpx.Response(401, json={}))
        r = client.post("/canvas/token", json={"token": "1234~abcdefghijklmnop"}, headers={"Authorization": f"Bearer {user_token}"})
    assert r.status_code == 400


def test_student_id_derivation():
    from app.canvas.client import student_id_of
    assert student_id_of({"sis_user_id": "111", "login_id": "999@mcpsmd.net"}) == "111"
    assert student_id_of({"login_id": "123456@mcpsmd.net"}) == "123456"
    assert student_id_of({"login_id": "jsmith@school.org", "integration_id": "777"}) == "777"
    assert student_id_of({"sis_user_id": "111", "login_id": "999@x"}, "login_id") == "999"


@respx.mock
async def test_find_student_matches_locally_even_if_search_term_is_ignored(monkeypatch):
    from app.mcp import canvas_server
    users = [{"id": 1, "name": "Ana Cruz", "sortable_name": "Cruz, Ana", "login_id": "123456@mcpsmd.net"},
             {"id": 2, "name": "Bo Lee", "sortable_name": "Lee, Bo", "login_id": "654321@mcpsmd.net"}]
    respx.get(f"{BASE}/api/v1/courses").mock(return_value=httpx.Response(200, json=[{"id": 5, "name": "ENL 1", "course_code": "E1"}]))
    respx.get(f"{BASE}/api/v1/courses/5/users").mock(return_value=httpx.Response(200, json=users))
    c = CanvasClient(BASE, "t")
    hits = await canvas_server._find(c, "123456")
    assert [h["student"]["name"] for h in hits] == ["Ana Cruz"]
    assert [h["student"]["name"] for h in await canvas_server._find(c, "lee")] == ["Bo Lee"]
    assert await canvas_server._find(c, "999999") == []
