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
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    @field_validator("database_url")
    @classmethod
    def require_postgresql(cls, value: str) -> str:
        if not value.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("DATABASE_URL must use PostgreSQL (postgresql:// or postgresql+psycopg://)")
        return value

    @model_validator(mode="after")
    def require_production_secret(self):
        if self.environment.lower() in {"production", "prod"}:
            if len(self.secret_key) < 32 or self.secret_key in {"change-this-before-production", "replace-with-a-long-random-secret"}:
                raise ValueError("Set SECRET_KEY to a unique random value of at least 32 characters in production")
        elif self.secret_key in {"change-this-before-production", "replace-with-a-long-random-secret"}:
            import warnings
            warnings.warn("Using default insecure SECRET_KEY in development. Please set a unique SECRET_KEY in your .env file.", UserWarning, stacklevel=2)
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

