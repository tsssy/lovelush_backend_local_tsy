"""Core application configuration module."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings."""

    # Application
    app_name: str = "LoveLush Backend"
    app_version: str = "1.0.0"
    app_root_path: str = ""
    debug: bool = True

    # Database
    mongo_uri: str = "mongodb://localhost:27017"
    mongodb_name: str = "lovelush"
    mongodb_username: str = ""
    mongodb_password: str = ""

    # Security
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # CORS
    cors_origins: list = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:5000",
        "http://127.0.0.1:5000",
        "file://",  # Allow file:// for local HTML files
        "null",  # Allow null origin for local files
    ]

    # Telegram Bot
    telegram_bot_token: str = ""
    telegram_webhook_url: str = ""
    telegram_webhook_secret: str = ""
    telegram_mini_app_url: str = ""

    # Proxy settings (for local development)
    http_proxy: str = ""
    https_proxy: str = ""

    # Soketi/Pusher configuration
    pusher_app_id: str = "app-id"
    pusher_key: str = "app-key"
    pusher_secret: str = "app-secret"
    pusher_cluster: str = "mt1"
    pusher_host: str = "127.0.0.1"  # Internal host for backend connections
    pusher_port: int = 6001  # Internal port for backend connections
    pusher_use_tls: bool = False  # Internal TLS (backend to soketi)
    pusher_external_host: str = (
        "pusher_default"  # External host for frontend clients (domain only)
    )
    pusher_external_ws_path: str = "/ws"  # WebSocket path for HTTP (ws://)
    pusher_external_wss_path: str = "/ws"  # WebSocket path for HTTPS (wss://)
    pusher_external_port: int = 6001  # External port (can be different from internal)
    pusher_external_use_tls: bool = True  # External TLS (frontend connections)

    # S3-compatible storage configuration (AWS S3, Cloudflare R2, etc.)
    s3_endpoint_url: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_bucket_name: str = ""
    s3_public_url: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
