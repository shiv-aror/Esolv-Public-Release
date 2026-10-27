from app.auth.google import _token_error, domain_allowed, session_email_allowed


def test_google_token_error_is_actionable_without_echoing_claims():
    code, message = _token_error("Token has wrong audience attacker@example.com, expected app client")
    assert code == "wrong_audience" and "different OAuth client" in message
    assert "attacker@example.com" not in message


def test_google_token_verification_allows_small_clock_skew(monkeypatch):
    from app.auth import google

    seen = {}
    def verify(token, request, audience, clock_skew_in_seconds):
        seen.update(token=token, audience=audience, skew=clock_skew_in_seconds)
        return {"email": "teacher@mcpsmd.org"}
    monkeypatch.setattr(google.g_id_token, "verify_oauth2_token", verify)
    assert google._verify_sync("test-token")["email"] == "teacher@mcpsmd.org"
    assert seen["skew"] == 60


def test_domain_rules():
    assert domain_allowed("a@mcpsmd.org", "mcpsmd.org")
    assert not domain_allowed("a@gmail.com", None)
    assert not domain_allowed("a@mcpsmd.org", "evil.com")
    assert not domain_allowed("a@evil.com", "mcpsmd.org")
    assert domain_allowed("AroraShivum@gmail.com", None)
    assert domain_allowed("srikarvinnamuri@gmail.com", None)
    assert not domain_allowed("somebodyelse@gmail.com", None)
    assert session_email_allowed("ARORASHIVUM@gmail.com")
    assert not session_email_allowed("somebodyelse@gmail.com")


def test_dev_login_and_me(client):
    c = client
    if True:
        r = c.post("/auth/dev", json={"email": "Teacher@mcpsmd.org", "name": "T"})
        assert r.status_code == 200
        tok = r.json()["token"]
        assert c.get("/me", headers={"Authorization": f"Bearer {tok}"}).json()["email"] == "teacher@mcpsmd.org"
        assert c.get("/me").status_code == 401
        assert c.get("/me", headers={"Authorization": "Bearer junk"}).status_code == 401
        assert c.post("/auth/dev", json={"email": "somebodyelse@gmail.com"}).status_code == 403


def test_existing_unapproved_session_is_rejected(client):
    from app.auth.sessions import issue_session
    token, _ = issue_session("somebodyelse@gmail.com", "Other")
    assert client.get("/me", headers={"Authorization": f"Bearer {token}"}).status_code == 403


def test_admin_requires_admin(user_token, client):
    c = client
    if True:
        assert c.post("/admin/ingest", headers={"Authorization": f"Bearer {user_token}"}).status_code == 403
        assert c.post("/admin/ingest").status_code == 401


def test_google_endpoint_rejects_garbage(client):
    c = client
    if True:
        assert c.post("/auth/google", json={"id_token": "not.a.jwt"}).status_code in (401, 503)
