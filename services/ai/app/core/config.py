import os
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # services/ai/app/core
env_mode = os.getenv("ENV", "development")
if env_mode == "local":
    ENV_FILE = BASE_DIR.parent / ".env.ai.private.local"
elif env_mode == "production":
    ENV_FILE = BASE_DIR.parent / ".env.ai.prod"
else:
    ENV_FILE = BASE_DIR.parent / ".env.ai.private.dev"


class Settings(BaseSettings):
    env: str = "development"
    debug: bool = True
    LOG_LEVEL: str = "INFO"

    ai_database_url: str
    REDIS_URL: str = "redis://localhost:6379"
    ANTHROPIC_API_KEY: str | None = None
    ENCRYPTION_KEY: str  # 32-byte base64-encoded secret for AES-256-GCM
    OLLAMA_URL: str | None = None
    OLLAMA_MODEL: str = "llama3.2"
    # JSON list of {"origin": "http://host:port", "allow_private": bool} — see
    # app/services/egress_policy.py. Operator-set only, never tenant-facing.
    AI_PROVIDER_APPROVED_ORIGINS: str | None = None
    AI_RATE_LIMIT_PER_HOUR: int = 100
    # Separate, much tighter cap on the GrantFlow-funded Excel-import
    # fallback specifically (see budget-export-from-excel design.md Decision
    # 5/Risks) — a real, currently-uncapped cost center distinct from the
    # general BYOK-covered AI_RATE_LIMIT_PER_HOUR above. Starting value, not
    # yet informed by real usage data.
    AI_EXCEL_IMPORT_PLATFORM_RATE_LIMIT_PER_HOUR: int = 10

    @field_validator("AI_PROVIDER_APPROVED_ORIGINS")
    @classmethod
    def _validate_approved_origins(cls, raw: str | None) -> str | None:
        # Fail at startup rather than 500 on every request.
        from app.services.egress_policy import parse_approved_origins

        parse_approved_origins(raw)
        return raw

    model_config = SettingsConfigDict(env_file=ENV_FILE, case_sensitive=False, extra="ignore")


settings = Settings()  # type: ignore[call-arg]
