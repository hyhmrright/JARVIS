from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Sensitive — must be provided via env vars or .env, no defaults
    database_url: str
    redis_url: str
    minio_access_key: str
    minio_secret_key: str
    jwt_secret: str
    encryption_key: str

    # LLM API keys — optional, used as fallback when user has no stored key
    deepseek_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    zhipuai_api_key: str = ""

    # Non-sensitive — safe defaults for local development
    qdrant_url: str = "http://localhost:6333"
    minio_endpoint: str = "localhost:9000"
    minio_bucket: str = "jarvis-documents"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days
    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
