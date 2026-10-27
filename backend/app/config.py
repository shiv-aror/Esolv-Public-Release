from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    env: str = "dev"
    dev_login: bool = False
    public_url: str = "http://localhost:8000"


    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "anthropic/claude-haiku-5.5"
    openrouter_fallback_model: str = "openai/gpt-5-nano"
    openrouter_zdr: bool = True
    max_tool_steps: int = 6


    google_client_id: str = ""
    allowed_domains: str = "mcpsmd.org"
    allowed_emails: str = ""
    admin_emails: str = ""
    jwt_secret: str = "change-me-in-dev-only"
    jwt_ttl_minutes: int = 480
    encryption_key: str = ""


    canvas_base_url: str = "https://mcpsmd.instructure.com"
    canvas_client_id: str = ""
    canvas_client_secret: str = ""
    canvas_redirect_uri: str = "http://localhost:8000/canvas/oauth/callback"
    canvas_mock: bool = False
    canvas_student_id_field: str = "auto"
    canvas_oauth_scopes: str = ""
    accommodations_provider: str = "csv"
    canvas_accommodations_column: str = "Accommodations"


    embeddings: str = "fastembed"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    rerank: bool = False
    rerank_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    min_relevance: float = 0.62
    top_k: int = 6


    data_dir: Path = BASE_DIR / "data"
    database_url: str = f"sqlite:///{BASE_DIR / 'esolv.db'}"
    audit_retention_days: int = 180


    chat_per_minute: int = 20
    max_image_bytes: int = 5 * 1024 * 1024
    max_images: int = 3
    max_file_bytes: int = 10 * 1024 * 1024
    max_files: int = 3
    max_file_chars: int = 24000
    max_message_chars: int = 6000

    @field_validator("data_dir", mode="before")
    @classmethod
    def _path(cls, v):
        return Path(v)

    @property
    def allowed_domain_list(self) -> list[str]:
        return [d.strip().lower() for d in self.allowed_domains.split(",") if d.strip()]

    @property
    def allowed_email_list(self) -> list[str]:
        return [e.strip().lower() for e in self.allowed_emails.split(",") if e.strip()]

    @property
    def admin_list(self) -> list[str]:
        return [e.strip().lower() for e in self.admin_emails.split(",") if e.strip()]

    @property
    def docs_dir(self) -> Path:
        return self.data_dir / "docs"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "models"

    @property
    def is_prod(self) -> bool:
        return self.env.lower() == "prod"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.is_prod and (s.dev_login or s.jwt_secret.startswith("change-me") or not s.encryption_key):
        raise RuntimeError("Refusing to start in prod with dev login, default JWT secret or no ENCRYPTION_KEY")
    return s
