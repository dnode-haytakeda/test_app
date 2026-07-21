from typing import Literal

from pydantic import Field, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="forbid",
    )

    # アプリケーション
    APP_ENV: Literal["development", "staging", "production"] = "development"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    TRUSTED_HOSTS: list[str] = []

    # データベース
    POSTGRES_USER: str = "user"
    POSTGRES_PASSWORD: SecretStr = SecretStr("password")
    POSTGRES_DB: str = "app_db"
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432
    POSTGRES_SSL: bool = False

    # バックエンド
    SECRET_KEY: SecretStr = Field(
        default=SecretStr("secret"),
        description="JWT signing key.",
    )
    JWT_ALGORITHM: Literal["HS256", "HS384", "HS512"] = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30

    @computed_field
    @property
    def database_url(self) -> str:
        query_params: dict[str, str] = {}
        if self.POSTGRES_SSL:
            query_params["ssl"] = "require"
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD.get_secret_value(),
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            database=self.POSTGRES_DB,
            query=query_params,
        ).render_as_string(hide_password=False)

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

settings = Settings()