import secrets
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres@localhost:5432/aura"
    jwt_secret_key: str = secrets.token_urlsafe(48)
    access_token_minutes: int = 720
    upload_dir: Path = Path("./data/uploads")
    max_upload_bytes: int = 20 * 1024 * 1024
    ollama_base_url: str = ""
    ollama_chat_model: str = "qwen2.5:7b"
    ollama_embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = 768
    cors_origins: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
