from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "order-service"
    app_version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"

    database_url: str = (
        "postgresql+psycopg://forge_order:forge_order_local_dev@localhost:5432/forge_orders"
    )
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=5, ge=0, le=50)
    db_connect_timeout_seconds: int = Field(default=5, ge=1, le=30)
    db_statement_timeout_ms: int = Field(default=5000, ge=500, le=60000)

    inventory_base_url: str = "http://localhost:8001"
    inventory_timeout_seconds: float = Field(default=3.0, ge=0.5, le=30.0)
    store_currency: str = "USD"

    max_request_bytes: int = Field(default=131_072, ge=1024, le=10_485_760)
    rate_limit_per_minute: int = Field(default=120, ge=0, le=100_000)
    cors_origins: str = "http://localhost:5173"

    @field_validator("store_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        value = value.strip().upper()
        if len(value) != 3 or not value.isalpha():
            raise ValueError("store_currency must be a three-letter ISO currency code")
        return value

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        value = value.strip().upper()
        if value not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("invalid log level")
        return value

    @field_validator("inventory_base_url")
    @classmethod
    def validate_inventory_url(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        if not value.startswith(("http://", "https://")):
            raise ValueError("inventory_base_url must be an HTTP(S) URL")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
