"""Application configuration loaded from environment variables.
 
This module defines a single `Settings` object, built with
pydantic-settings, that the rest of the application should import
instead of reading `os.environ` directly. This keeps configuration
parsing (types, defaults, validation) in one place.
"""
 
from __future__ import annotations
 
from pydantic_settings import BaseSettings, SettingsConfigDict
 
 
class Settings(BaseSettings):
    """Runtime configuration for the application.
 
    Values are read from environment variables (or a `.env` file) and
    fall back to development-friendly defaults when unset.
    """
 
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )
 
    ENVIRONMENT: str = "development"
 
    # Raw comma-separated string from the environment. Use the
    # `cors_origins_list` property below to get a parsed list[str].
    CORS_ORIGINS: str = "http://localhost:5173"
 
    MODEL_CACHE_DIR: str = "./models_cache"
    MAX_IMAGE_SIDE: int = 1600
    LOG_LEVEL: str = "INFO"
    OFFLINE_MODE: bool = False
 
    @property
    def cors_origins_list(self) -> list[str]:
        """Return CORS_ORIGINS parsed into a list of origin strings.
 
        Splits on commas and strips whitespace from each entry, dropping
        any empty values produced by trailing commas or blank input.
        """
        return [
            origin.strip()
            for origin in self.CORS_ORIGINS.split(",")
            if origin.strip()
        ]
 
 
settings = Settings()
 