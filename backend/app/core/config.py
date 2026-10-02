"""Application configuration loaded from environment variables / .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SOC Detection Platform"
    app_version: str = "0.1.0"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    # Comma-separated string (simple to set in .env on any OS)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # MongoDB. Defaults suit a local, unauthenticated development instance.
    # Real credentials belong in the git-ignored .env file, never in code.
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "soc_detection_platform"
    mongodb_server_selection_timeout_ms: int = 3000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
