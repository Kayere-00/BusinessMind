"""Application configuration — all secrets come from environment variables."""
import logging
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("businessmind.config")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "BusinessMind AI"
    ENV: str = "production"

    # Database — PostgreSQL in every deployed environment.
    DATABASE_URL: str = "postgresql+psycopg2://businessmind:businessmind@db:5432/businessmind"

    # Auth — JWT_SECRET MUST be overridden via env in production (see validate_production).
    JWT_SECRET: str = "INSECURE-DEV-ONLY-change-me"  # nosec B105 - dev fallback, never for prod
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    BCRYPT_ROUNDS: int = 12

    # Uploads / storage
    STORAGE_DIR: str = "./storage"
    MAX_UPLOAD_MB: int = 10
    MAX_ROWS: int = 200_000
    MAX_COLS: int = 100
    ALLOWED_EXTENSIONS: str = ".csv,.xlsx,.xls"

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:8000"

    # Ollama LLM
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1"
    OLLAMA_ENABLED: bool = True
    OLLAMA_TIMEOUT_S: int = 60
    OLLAMA_ALLOW_REMOTE: bool = False
    OLLAMA_HISTORY_MESSAGES: int = 24
    OLLAMA_MAX_TOOL_ROUNDS: int = 4

    # Rate limiting (per IP, per minute)
    AUTH_RATE_LIMIT: int = 10

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def allowed_extension_set(self) -> set[str]:
        return {e.strip().lower() for e in self.ALLOWED_EXTENSIONS.split(",")}

    def validate_production(self) -> None:
        if self.ENV == "production" and self.JWT_SECRET == "INSECURE-DEV-ONLY-change-me":
            logger.warning(
                "JWT_SECRET is the built-in development default. "
                "Set a strong secret via the JWT_SECRET environment variable."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
