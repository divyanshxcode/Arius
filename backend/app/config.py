"""Arius broker configuration.

All settings come from the environment (or backend/.env). Defaults match
docker-compose.yml so a fresh checkout talks to the containers out of the box.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Transactional state — YugabyteDB (Postgres wire protocol on 5433)
    yb_url: str = "postgresql+psycopg://yugabyte:yugabyte@localhost:5433/arius"

    # Time-series telemetry — Tiger Data (TimescaleDB image).
    # Host port 5434: 5432 is commonly taken by a local PostgreSQL install.
    td_url: str = "postgresql+psycopg://arius:arius@localhost:5434/arius"

    # auto = Yugabyte, else SQLite dev fallback | yugabyte = required | sqlite = forced
    db_mode: str = "auto"
    sqlite_path: str = "arius_dev.db"

    gemini_api_key: str = ""
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
