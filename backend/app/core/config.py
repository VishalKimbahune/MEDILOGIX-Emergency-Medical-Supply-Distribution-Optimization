"""
Application configuration loaded via environment variables.

Supports PostgreSQL for production and SQLite for local development.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration settings for the MEDILOGIX FastAPI backend."""

    app_name: str = "MEDILOGIX API"
    app_version: str = "0.1.0"
    app_env: str = "development"
    debug: bool = True

    # Database
    database_url: str = "sqlite:///./medilogix_dev.db"

    # CORS
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Configurable geographical scope (Pune Urban & PCMC default; expandable to Pune district)
    geo_region_name: str = "Pune Urban & Pimpri-Chinchwad"
    geo_min_lat: float = 18.40
    geo_max_lat: float = 18.70
    geo_min_lon: float = 73.70
    geo_max_lon: float = 74.05

    # Dataset path
    synthetic_data_dir: str = str(
        (Path(__file__).resolve().parents[3] / "data" / "synthetic").resolve()
    )

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a clean list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
