from pathlib import Path

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

    # Tool API keys — optional, used as server-level fallback
    tavily_api_key: str = ""

    # Channel bot tokens — optional, leave empty to disable the channel
    telegram_bot_token: str = ""
    telegram_webhook_url: str = ""
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    discord_bot_token: str = ""
    slack_bot_token: str = ""
    slack_app_token: str = ""
    whatsapp_account_sid: str = ""
    whatsapp_auth_token: str = ""
    whatsapp_from_number: str = "whatsapp:+14155238886"  # Twilio sandbox default

    # Non-sensitive — safe defaults for local development
    qdrant_url: str = "http://localhost:6333"
    minio_endpoint: str = "localhost:9000"
    minio_bucket: str = "jarvis-documents"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 30  # 30 days
    cors_origins: list[str] = ["http://localhost:3000"]
    log_level: str = "INFO"

    # Skills directory — load .md skill files to inject into system prompt
    skills_dir: str = str(Path.home() / ".jarvis" / "skills")

    # Local memory sync — export conversations to Markdown files
    memory_sync_dir: str = str(Path.home() / ".jarvis" / "memory")

    # MCP server configurations (JSON array of MCPServerConfig dicts)
    mcp_servers_json: str = ""

    # Sandbox settings
    sandbox_enabled: bool = False
    sandbox_image: str = "jarvis-sandbox:latest"
    sandbox_cpu_limit: float = 1.0
    sandbox_memory_limit: str = "512m"
    sandbox_timeout: int = 300


settings = Settings()
