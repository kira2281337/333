from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки читаются из переменных окружения / файла .env."""

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/shortener"
    # Значение по умолчанию только для разработки; в проде задаётся через SECRET_KEY.
    secret_key: str = "dev-only-secret-key-change-me-in-production-0123456789"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

# Лимиты активных ссылок по роли пользователя.
LINK_LIMITS: dict[str, int] = {"user": 3, "premium": 5}
