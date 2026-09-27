import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # services/budget/app/core
# ENV_FILE = BASE_DIR.parent / ".env.budget.dev"
# Determine which env file to load based on environment
env_mode = os.getenv("ENV", "development")
if env_mode == "local":
    ENV_FILE = BASE_DIR.parent / ".env.budget.private.local"
elif env_mode == "production":
    ENV_FILE = BASE_DIR.parent / ".env.budget.prod"
else:
    ENV_FILE = BASE_DIR.parent / ".env.budget.private.dev"


class Settings(BaseSettings):
    env: str = "development"
    debug: bool = True

    # Service URLs
    customer_service_url: str
    donor_grantee_service_url: str
    user_service_url: str
    user_all_services_url: str
    # Databases
    budget_database_url: str
    REDIS_URL: str
    # Object storage (S3-compatible: MinIO locally, Cloudflare R2 in production)
    STORAGE_ENDPOINT_URL: str
    STORAGE_ACCESS_KEY: str
    STORAGE_SECRET_KEY: str
    STORAGE_BUCKET_NAME: str
    # RabbitMQ
    RABBITMQ_URL: str
    RABBITMQ_EXCHANGE: str
    RABBITMQ_QUEUE: str
    LOG_LEVEL: str
    # Sent as X-Internal-Service-Token to the users service (see
    # shared/security/internal_service.py).
    INTERNAL_SERVICE_TOKEN: str = ""

    model_config = SettingsConfigDict(env_file=ENV_FILE, case_sensitive=False, extra="ignore")


settings = Settings()  # type: ignore[call-arg]
