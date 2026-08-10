"""Application settings.

Reads every variable listed in `backend/.env.example`. Broker/LLM provider
keys are optional (default None) since they are not wired up until later
phases; DB/Redis-independent code paths must work without them.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────
    ENVIRONMENT: str = "development"
    APP_SECRET_KEY: str
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: str = "http://localhost:3000"

    # ── Supabase ─────────────────────────────────────────────────────
    SUPABASE_URL: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None
    # Newer Supabase projects sign access tokens with a per-project asymmetric
    # key (ES256), verified via the public JWKS endpoint derived from
    # SUPABASE_URL — no secret required for that path. SUPABASE_JWT_SECRET is
    # only the legacy HS256 shared secret, kept as a fallback verification
    # path. At least one of the two must be configured.
    SUPABASE_JWT_SECRET: Optional[str] = None
    DATABASE_URL: str

    # ── Redis ────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── LLM providers ────────────────────────────────────────────────
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: Optional[str] = "gpt-4.1-mini"
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: Optional[str] = "llama-3.3-70b-versatile"
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: Optional[str] = "gemini-2.0-flash"
    EMBEDDING_MODEL: Optional[str] = "text-embedding-3-small"

    # ── Broker adapters ──────────────────────────────────────────────
    DHAN_CLIENT_ID: Optional[str] = None
    DHAN_ACCESS_TOKEN: Optional[str] = None
    ANGELONE_API_KEY: Optional[str] = None
    ANGELONE_CLIENT_CODE: Optional[str] = None
    ANGELONE_PASSWORD: Optional[str] = None
    ANGELONE_TOTP_SECRET: Optional[str] = None
    UPSTOX_API_KEY: Optional[str] = None
    UPSTOX_API_SECRET: Optional[str] = None
    UPSTOX_REDIRECT_URI: Optional[str] = None
    FYERS_CLIENT_ID: Optional[str] = None
    FYERS_SECRET_KEY: Optional[str] = None
    FYERS_REDIRECT_URI: Optional[str] = None

    # ── Rate limiting ────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 60

    @field_validator("CORS_ORIGINS")
    @classmethod
    def _validate_cors(cls, v: str) -> str:
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def supabase_jwks_url(self) -> Optional[str]:
        if not self.SUPABASE_URL:
            return None
        return f"{self.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"

    @model_validator(mode="after")
    def _require_jwt_verification_path(self) -> "Settings":
        if not self.SUPABASE_URL and not self.SUPABASE_JWT_SECRET:
            raise ValueError(
                "Set SUPABASE_URL (for JWKS/ES256 verification) or "
                "SUPABASE_JWT_SECRET (legacy HS256 fallback), or both."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor. Import-time safe even with placeholder values —
    no network/DB connection is made here."""
    return Settings()
