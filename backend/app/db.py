from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlmodel import Field, Session, SQLModel, create_engine

from .config import get_settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    email: str = Field(primary_key=True)
    name: str = ""
    picture: str = ""
    created_at: datetime = Field(default_factory=utcnow)
    last_login: datetime = Field(default_factory=utcnow)


class CanvasCredential(SQLModel, table=True):
    user_email: str = Field(primary_key=True)
    kind: str = "pat"
    base_url: str = ""
    access_enc: str = ""
    refresh_enc: str = ""
    expires_at: datetime | None = None
    updated_at: datetime = Field(default_factory=utcnow)


class AuditLog(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=utcnow, index=True)
    user_email: str = Field(index=True)
    action: str
    detail: str = ""


class Feedback(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=utcnow)
    user_email: str
    rating: str
    comment: str = ""


_engine = None


def get_engine():
    global _engine
    if _engine is None:
        url = get_settings().database_url
        _engine = create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
        SQLModel.metadata.create_all(_engine)
    return _engine


def reset_engine():
    global _engine
    _engine = None


def session() -> Session:
    return Session(get_engine())


def audit(user_email: str, action: str, detail: str = "") -> None:
    with session() as s:
        s.add(AuditLog(user_email=user_email, action=action, detail=detail[:500]))
        s.commit()


def purge_old_audit() -> None:
    cutoff = utcnow() - timedelta(days=get_settings().audit_retention_days)
    with session() as s:
        s.exec(text("DELETE FROM auditlog WHERE ts < :c").bindparams(c=cutoff.strftime("%Y-%m-%d %H:%M:%S.%f")))
        s.commit()
