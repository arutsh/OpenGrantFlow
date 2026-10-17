import os
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # services/ai/app/core
REPO_ROOT = BASE_DIR.parent.parent.parent  # repo root on bare-metal; "/" inside the container
env_mode = os.getenv("ENV", "development")
if env_mode == "local":
    ENV_FILE = BASE_DIR.parent / ".env.ai.private.local"
elif env_mode == "production":
    ENV_FILE = BASE_DIR.parent / ".env.ai.prod"
else:
    ENV_FILE = BASE_DIR.parent / ".env.ai.private.dev"


def _site_knowledge_default(container_path: str, repo_relative: str) -> str:
    # The Dockerfile COPYs sources to container_path; bare-metal dev has no
    # such copy, so fall back to the original location under the repo root.
    if Path(container_path).exists():
        return container_path
    return str(REPO_ROOT / repo_relative)


# Site-assistant (per-IP, global) daily caps per provider; None means no cap.
CAP_PROFILES: dict[str, tuple[int | None, int | None]] = {
    "anthropic": (20, 300),
    "ollama": (200, None),
}
HUMAN_VERIFIERS = {"none"}


def resolve_daily_cap(override: int | None, profile_default: int | None) -> int | None:
    """Effective cap: an unset override uses the profile, and 0 means unlimited (None)."""
    cap = profile_default if override is None else override
    return cap or None


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
    # Paths the Dockerfile COPYs the site-knowledge-index sources to.
    SITE_CONTENT_DIR: str = _site_knowledge_default(
        "/app/content/site", "frontend-typescript/src/content/site"
    )
    GUIDE_DOCS_DIR: str = _site_knowledge_default("/app/docs/user-guide", "docs/user-guide")
    PRODUCT_DOC_PATH: str = _site_knowledge_default("/app/docs/PRODUCT.md", "docs/PRODUCT.md")

    SITE_ASSISTANT_ENABLED: bool = False
    SITE_ASSISTANT_PROVIDER: str = "anthropic"
    SITE_ASSISTANT_MODEL: str | None = None
    SITE_ASSISTANT_PER_IP_DAILY_CAP: int | None = Field(default=None, ge=0)
    SITE_ASSISTANT_GLOBAL_DAILY_CAP: int | None = Field(default=None, ge=0)
    SITE_ASSISTANT_MAX_QUESTION_CHARS: int = Field(default=500, ge=1)
    SITE_ASSISTANT_TOP_K: int = Field(default=5, ge=1)
    # Matches tests/evals/baseline.yaml unanswerable_threshold.
    SITE_ASSISTANT_MIN_SCORE: float = 0.25
    SITE_ASSISTANT_HUMAN_VERIFIER: str = "none"
    # Comma-separated hosts an answer may link to; any other link fails the answer closed.
    SITE_ASSISTANT_LINK_HOSTS: str = "opengrantflow.com,www.opengrantflow.com"

    @field_validator("SITE_ASSISTANT_PROVIDER")
    @classmethod
    def _validate_site_assistant_provider(cls, provider: str) -> str:
        if provider not in CAP_PROFILES:
            raise ValueError(f"SITE_ASSISTANT_PROVIDER must be one of {sorted(CAP_PROFILES)}")
        return provider

    @field_validator(
        "SITE_ASSISTANT_PER_IP_DAILY_CAP", "SITE_ASSISTANT_GLOBAL_DAILY_CAP", mode="before"
    )
    @classmethod
    def _blank_cap_is_unset(cls, value: object) -> object:
        # An empty env value (`CAP=`) means "use the profile default", not a parse error.
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("SITE_ASSISTANT_HUMAN_VERIFIER")
    @classmethod
    def _validate_human_verifier(cls, verifier: str) -> str:
        if verifier not in HUMAN_VERIFIERS:
            raise ValueError(f"SITE_ASSISTANT_HUMAN_VERIFIER must be one of {HUMAN_VERIFIERS}")
        return verifier

    @property
    def site_assistant_link_hosts(self) -> frozenset[str]:
        hosts = self.SITE_ASSISTANT_LINK_HOSTS.split(",")
        return frozenset(h.strip().lower() for h in hosts if h.strip())

    @property
    def site_assistant_per_ip_cap(self) -> int | None:
        profile = CAP_PROFILES[self.SITE_ASSISTANT_PROVIDER][0]
        return resolve_daily_cap(self.SITE_ASSISTANT_PER_IP_DAILY_CAP, profile)

    @property
    def site_assistant_global_cap(self) -> int | None:
        profile = CAP_PROFILES[self.SITE_ASSISTANT_PROVIDER][1]
        return resolve_daily_cap(self.SITE_ASSISTANT_GLOBAL_DAILY_CAP, profile)

    @field_validator("AI_PROVIDER_APPROVED_ORIGINS")
    @classmethod
    def _validate_approved_origins(cls, raw: str | None) -> str | None:
        # Fail at startup rather than 500 on every request.
        from app.services.egress_policy import parse_approved_origins

        parse_approved_origins(raw)
        return raw

    model_config = SettingsConfigDict(env_file=ENV_FILE, case_sensitive=False, extra="ignore")


settings = Settings()  # type: ignore[call-arg]
