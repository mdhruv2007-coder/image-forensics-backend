from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENVIRONMENT: str = "development"
    CORS_ORIGINS: str = "http://localhost:5173"
    MODEL_CACHE_DIR: str = "./models_cache"
    MAX_IMAGE_SIDE: int = 1600
    LOG_LEVEL: str = "INFO"
    OFFLINE_MODE: bool = False

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()