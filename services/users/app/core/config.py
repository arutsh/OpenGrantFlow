import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # services/users/app/core

# Environment-aware env file selection
ENV = os.getenv("ENV", "development")
if ENV == "local":
    ENV_FILE = BASE_DIR.parent / ".env.users.local"
elif ENV == "production":
    ENV_FILE = BASE_DIR.parent / ".env.users.prod"
else:
    ENV_FILE = BASE_DIR.parent / ".env.users.dev"


class Settings(BaseSettings):
    env: str = "development"
    debug: bool = True
    users_database_url: str
    REDIS_URL: str
    RABBITMQ_URL: str
    RABBITMQ_EXCHANGE: str
    LOG_LEVEL: str
    AI_SERVICE_URL: str = "http://localhost:8082/api/v1"
    BUDGET_SERVICE_URL: str = "http://localhost:8001/api/v1"
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_SECONDS: int = 900
    # Object storage (S3-compatible: MinIO locally, Cloudflare R2 in production)
    STORAGE_ENDPOINT_URL: str
    STORAGE_ACCESS_KEY: str
    STORAGE_SECRET_KEY: str
    STORAGE_BUCKET_NAME: str
    # Only ever true in .env.users.local (local dev + e2e CI, both boot from
    # docker-compose.local.yml) — never set in .env.users.dev/.env.users.prod.
    # Lets e2e drive the real /auth/verify-email flow without a real inbox.
    EXPOSE_VERIFICATION_TOKEN_FOR_TESTS: bool = False
    # Shared secret budget/ai/chat send on service-to-service calls (see
    # shared/security/internal_service.py); empty means "reject everything".
    INTERNAL_SERVICE_TOKEN: str = ""
    model_config = SettingsConfigDict(env_file=ENV_FILE, case_sensitive=False, extra="ignore")


settings = Settings()  # type: ignore[call-arg]

# pydantic-settings reads env_file into this object only, not into os.environ —
# shared/security/internal_service.py reads the raw env var, so export it here.
os.environ.setdefault("INTERNAL_SERVICE_TOKEN", settings.INTERNAL_SERVICE_TOKEN)
