from functools import lru_cache
from urllib.parse import urlparse
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator, Field, AliasChoices


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    app_env: str = 'development'
    database_url: str = 'postgresql+psycopg://dentflow:dentflow@localhost:5432/dentflow_devstand'
    redis_url: str = ''
    enable_dev_tools: bool = False
    cookie_secure: bool = False
    allowed_origins: str = 'http://localhost:8080,http://localhost:3000,http://127.0.0.1:8080,http://127.0.0.1:3000'
    session_hours: int = 12
    visitor_days: int = 30
    ai_provider: str = 'demo'
    timezone: str = 'Europe/Moscow'
    auto_seed: bool = False
    telegram_bot_token: str = ''
    telegram_tenant_slug: str = Field(default='smile-avenue', validation_alias=AliasChoices('TELEGRAM_CLINIC_SLUG', 'TELEGRAM_TENANT_SLUG'))
    telegram_webhook_secret: str = ''
    public_base_url: str = Field(default='http://localhost:8080', validation_alias=AliasChoices('PUBLIC_URL', 'PUBLIC_BASE_URL'))
    allow_external_ai: bool = Field(default=False, validation_alias=AliasChoices('AI_EXTERNAL_ENABLED', 'ALLOW_EXTERNAL_AI'))
    secret_key: str = ''
    log_level: str = 'INFO'

    @property
    def origins(self) -> list[str]:
        return [x.strip().rstrip('/') for x in self.allowed_origins.split(',') if x.strip()]

    @property
    def is_demo(self) -> bool:
        return self.app_env in {'development', 'devstand', 'test'}

    @property
    def dev_tools(self) -> bool:
        return self.is_demo and self.enable_dev_tools

    @model_validator(mode='after')
    def validate_environment(self):
        if self.app_env not in {'development', 'devstand', 'production', 'test'}:
            raise ValueError('APP_ENV: допустимы development, devstand, production, test')
        if self.database_url.startswith('sqlite') and self.app_env != 'test':
            raise ValueError('SQLite разрешён только для тестов. Укажите PostgreSQL DATABASE_URL.')
        if self.app_env == 'production':
            if len(self.secret_key) < 32 or 'change_me' in self.secret_key.lower() or 'demo' in self.secret_key.lower():
                raise ValueError('SECRET_KEY production должен быть уникальным случайным секретом не короче 32 символов')
            if self.enable_dev_tools or self.auto_seed:
                raise ValueError('В production запрещены ENABLE_DEV_TOOLS и AUTO_SEED')
            if not self.cookie_secure:
                raise ValueError('В production обязателен COOKIE_SECURE=true и HTTPS')
            if not self.origins or any(not x.startswith('https://') or '*' in x for x in self.origins):
                raise ValueError('ALLOWED_ORIGINS production должен содержать точные HTTPS origins')
            name = urlparse(self.database_url).path.lstrip('/')
            if name in {'dentflow_dev', 'dentflow_devstand', 'dentflow_test'} or not name:
                raise ValueError('Production требует отдельную БД, отличную от dev/test')
            if not self.redis_url:
                raise ValueError('REDIS_URL обязателен в production для общего rate limit')
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
