from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "API Questões de Hanseníase"
    database_url: str = "sqlite:///./hanseniase.db"
    secret_key: str = "troque-esta-chave-em-producao"
    access_token_minutes: int = 60 * 8
    admin_email: str = "admin@example.com"
    admin_password: str = "admin123"
    cors_origins: str = "*"  # lista separada por vírgula
    seed_on_startup: bool = True

    @property
    def sqlalchemy_url(self) -> str:
        # Render entrega "postgres://..." ou "postgresql://..."; usamos o driver psycopg 3
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        return url

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
