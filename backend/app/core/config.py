from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://jarvis:jarvis@localhost:5432/jarvis"
    redis_url: str = "redis://localhost:6379"
    qdrant_url: str = "http://localhost:6333"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "changeme123"
    minio_bucket: str = "jarvis-documents"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days
    # Fernet key; override via env var in production.
    # Generate with: Fernet.generate_key().decode()
    # WARNING: default is not a valid Fernet key; a padded fallback is used.
    encryption_key: str = "V2hhdCBhIG5pY2UgZGF5IHRvIGZpeCBidWdzISEh"

    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
