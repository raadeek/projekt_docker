import os
from dataclasses import dataclass
from pathlib import Path


def _read_secret(path_env_name: str, fallback_env_name: str) -> str:
    secret_path = os.getenv(path_env_name)
    if secret_path:
        return Path(secret_path).read_text(encoding="utf-8").strip()

    fallback_value = os.getenv(fallback_env_name)
    if fallback_value:
        return fallback_value

    raise RuntimeError(f"Missing secret: set {path_env_name} or {fallback_env_name}")


@dataclass(frozen=True)
class Settings:
    app_name: str
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    redis_host: str
    redis_port: int
    redis_ttl_seconds: int


def load_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", "Tasks API"),
        db_host=os.getenv("DB_HOST", "localhost"),
        db_port=int(os.getenv("DB_PORT", "5432")),
        db_name=os.getenv("DB_NAME", "tasksdb"),
        db_user=os.getenv("DB_USER", "tasksuser"),
        db_password=_read_secret("DB_PASSWORD_FILE", "DB_PASSWORD"),
        redis_host=os.getenv("REDIS_HOST", "localhost"),
        redis_port=int(os.getenv("REDIS_PORT", "6379")),
        redis_ttl_seconds=int(os.getenv("REDIS_TTL_SECONDS", "30")),
    )


settings = load_settings()
