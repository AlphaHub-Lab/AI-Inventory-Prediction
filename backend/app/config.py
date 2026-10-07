from functools import lru_cache
from pathlib import Path
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "Inventory Intelligence API"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://inventory:inventory@localhost:5432/inventory"
    secret_key: str = "change-this-before-production"
    access_token_minutes: int = 30
    refresh_token_days: int = 14
    cors_origins: str = "http://localhost:5173"
    llm_api_key: str | None = None
    llm_model: str = "Llama-V3p2-3b-Reasoning"
    llm_base_url: str = "https://api.nugen.in/api/v3"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_use_ssl: bool = False
    skip_alembic_startup: bool = True
    supabase_url: str | None = None
    supabase_publishable_key: str | None = None
    supabase_secret_key: str | None = None
    supabase_jwks_url: str | None = None
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    @field_validator("database_url")
    @classmethod
    def require_postgresql(cls, value: str) -> str:
        if not value.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("DATABASE_URL must use PostgreSQL (postgresql:// or postgresql+psycopg://)")
        return value

    @model_validator(mode="after")
    def require_production_secret(self):
        if len(self.secret_key) < 32 or self.secret_key in {"change-this-before-production", "replace-with-a-long-random-secret"}:
            import warnings, secrets
            warnings.warn("Using default or weak SECRET_KEY. Please configure SECRET_KEY in your Vercel Project Settings.", UserWarning, stacklevel=2)
            if self.environment.lower() in {"production", "prod"}:
                # Provide a persistent-per-runtime random secret to avoid crashing cold starts
                self.secret_key = "prod-fallback-" + secrets.token_hex(24)
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [item.strip() for item in self.cors_origins.split(",") if item.strip()]
        for default in ["http://localhost:5173", "http://127.0.0.1:5173"]:
            if default not in origins:
                origins.append(default)
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()

