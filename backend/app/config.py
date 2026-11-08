from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FINDIT_")

    app_name: str = "FindIt"
    environment: str = "local"
    cors_origins: list[str] = ["http://localhost:5173"]
    database_url: str = "postgresql+psycopg://findit:findit@localhost:5432/findit"
    oidc_issuer: str = "http://localhost:8000/dev-sso"
    oidc_audience: str = "findit"
    oidc_jwks_url: str | None = None
    campus_id_hash_key: str = "dev-only-change-me"


@lru_cache
def get_settings() -> Settings:
    return Settings()
