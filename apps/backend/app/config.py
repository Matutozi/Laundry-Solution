from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://ghebee:wisewash@127.0.0.1:5432/wisewash"
    test_database_url: str = "postgresql+asyncpg://ghebee:wisewash@127.0.0.1:5432/wisewash_test"
    redis_url: str = "redis://localhost:6379/0"
    debug: bool = False

    secret_key: str = "change-me-in-production-min-32-chars!!"
    access_token_expire_minutes: int = 60
    pin_token_expire_minutes: int = 15


settings = Settings()
