from typing import Annotated, Literal, Self

from pydantic import Field, SecretStr, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy import URL

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="forbid",
    )

    # データベース
    POSTGRES_USER: str = "user"
    POSTGRES_PASSWORD: SecretStr = SecretStr("password")
    POSTGRES_DB: str = "app_db"
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432
    POSTGRES_HOST_PORT: int = 5432
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
    DATABASE_POOL_TIMEOUT: int = 5

    @computed_field
    @property
    def database_url(self) -> str:
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD.get_secret_value(),
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            database=self.POSTGRES_DB,
        ).render_as_string(hide_password=False)

settings = Settings()