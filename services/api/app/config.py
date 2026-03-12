"""API service configuration via Pydantic Settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+psycopg://postgres:postgres@postgres:5432/trading-automata"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # JWT
    jwt_secret: str  # Required — no default
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # Credential encryption
    fernet_key: str  # Required — no default

    # Root user bootstrap
    root_username: str = "root"
    root_password: str = ""  # Empty = generate random token

    # CORS
    cors_origins: str = "http://localhost:3000"  # Comma-separated

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    # Observability
    sentry_dsn: str = ""  # Optional — leave empty to disable
    environment: str = "development"

    model_config = {"env_prefix": "", "case_sensitive": False}

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def async_database_url(self) -> str:
        """Convert database URL to async-compatible format."""
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://") and "+psycopg" not in url:
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url


settings = Settings()
