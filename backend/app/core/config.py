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

    # CORS & Frontend URL
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    frontend_base_url: str = "http://localhost:5173"

    # Authentication & JWT Security (set JWT_SECRET_KEY in .env for production!)
    jwt_secret_key: str = "dev-only-change-me-in-env-medilogix-jwt-secret-key-32bytes"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    password_reset_expire_minutes: int = 30
    email_verification_expire_hours: int = 24
    auth_cookie_secure: bool = False
    auth_cookie_samesite: str = "lax"
    login_rate_limit_attempts: int = 10
    login_rate_limit_window_sec: int = 300

    # SMTP Email Delivery (optional; console link fallback used in development when unset)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "no-reply@medilogix.local"
    smtp_use_tls: bool = True

    # Configurable geographical scope (Pune Urban & PCMC default; expandable to Pune district)
    geo_region_name: str = "Pune Urban & Pimpri-Chinchwad"
    geo_min_lat: float = 18.40
    geo_max_lat: float = 18.70
    geo_min_lon: float = 73.70
    geo_max_lon: float = 74.05

    # Dataset & OSM road-network cache paths
    synthetic_data_dir: str = str(
        (Path(__file__).resolve().parents[3] / "data" / "synthetic").resolve()
    )
    osm_overpass_url: str = "https://overpass-api.de/api/interpreter"
    osm_cache_file: str = str(
        (
            Path(__file__).resolve().parents[3]
            / "data"
            / "processed"
            / "pune_osm_road_graph.json"
        ).resolve()
    )
    osm_request_timeout_sec: int = 65
    osm_max_snap_distance_km: float = 2.5
    osm_user_agent: str = "MEDILOGIX-Academic-OR-Prototype/1.0 (Pune Emergency Logistics Research)"

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
