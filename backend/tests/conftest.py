import os
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_tmp = Path(tempfile.mkdtemp(prefix="esolv-test-"))
shutil.copytree(ROOT / "data", _tmp / "data")
os.environ.update({
    "ENV": "dev", "DEV_LOGIN": "true", "EMBEDDINGS": "hash", "MIN_RELEVANCE": "0.2",
    "DATA_DIR": str(_tmp / "data"), "DATABASE_URL": f"sqlite:///{_tmp / 'test.db'}",
    "JWT_SECRET": "test-secret-test-secret-test-secret", "CANVAS_MOCK": "true", "OPENROUTER_API_KEY": "sk-test",
    "ALLOWED_DOMAINS": "mcpsmd.org", "ALLOWED_EMAILS": "arorashivum@gmail.com,srikarvinnamuri@gmail.com",
    "ADMIN_EMAILS": "admin@mcpsmd.org", "GOOGLE_CLIENT_ID": "test-client",
    "CHAT_PER_MINUTE": "1000", "ACCOMMODATIONS_PROVIDER": "csv",
})

import pytest


@pytest.fixture(scope="session", autouse=True)
def ingested():
    from app.rag import ingest
    stats = ingest.run()
    assert stats["chunks"] > 5
    return stats


@pytest.fixture
def user_token():
    from app.auth.sessions import issue_session
    return issue_session("teacher@mcpsmd.org", "Test Teacher")[0]


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c
