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
    encryption_key: str | None = None

    # BE-7: фото найденных вещей (в docker-compose это volume photos)
    photo_storage_dir: str = "storage/photos"
    photo_max_bytes: int = 5 * 1024 * 1024  # одно фото не больше 5 МБ
    photo_storage_limit_bytes: int = 10 * 1024**3  # C-01: всё хранилище не больше 10 ГБ
    photos_per_item: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
