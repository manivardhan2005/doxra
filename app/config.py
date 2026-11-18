"""Application configuration and environment variable management."""

import os
from functools import lru_cache
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self) -> None:
        self.app_name: str = "Automated Multi-Platform Posting System"
        self.app_version: str = "1.0.0"
        self.environment: str = os.getenv("ENVIRONMENT", "development")
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")
        self.host: str = os.getenv("HOST", "0.0.0.0")
        self.port: int = int(os.getenv("PORT", "4000"))
        self.request_timeout: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "10.0"))

        # Master Mock / Simulation Mode
        # If True, platforms without valid live credentials simulate successful responses.
        self.mock_mode: bool = os.getenv("MOCK_MODE", "true").lower() in ("true", "1", "yes")

        # Telegram Configuration
        self.telegram_bot_token: Optional[str] = os.getenv("TELEGRAM_BOT_TOKEN") or None
        self.telegram_chat_id: Optional[str] = os.getenv("TELEGRAM_CHAT_ID") or None
        self.telegram_channel_username: str = os.getenv("TELEGRAM_CHANNEL_USERNAME", "dxoratech")

        # Discord Configuration
        self.discord_webhook_url: Optional[str] = os.getenv("DISCORD_WEBHOOK_URL") or None

        # Slack Configuration
        self.slack_webhook_url: Optional[str] = os.getenv("SLACK_WEBHOOK_URL") or None

        # X (Twitter) Configuration
        self.twitter_bearer_token: Optional[str] = os.getenv("TWITTER_BEARER_TOKEN") or None
        self.twitter_api_key: Optional[str] = os.getenv("TWITTER_API_KEY") or None
        self.twitter_api_secret: Optional[str] = os.getenv("TWITTER_API_SECRET") or None
        self.twitter_access_token: Optional[str] = os.getenv("TWITTER_ACCESS_TOKEN") or None
        self.twitter_access_token_secret: Optional[str] = os.getenv("TWITTER_ACCESS_TOKEN_SECRET") or None
        self.twitter_username: str = os.getenv("TWITTER_USERNAME", "dxoratech")

        # Mastodon Configuration
        self.mastodon_instance_url: str = os.getenv("MASTODON_INSTANCE_URL", "https://mastodon.social").rstrip("/")
        self.mastodon_access_token: Optional[str] = os.getenv("MASTODON_ACCESS_TOKEN") or None
        self.mastodon_username: str = os.getenv("MASTODON_USERNAME", "dxora")

        # LinkedIn Configuration
        self.linkedin_access_token: Optional[str] = os.getenv("LINKEDIN_ACCESS_TOKEN") or None
        self.linkedin_author_urn: str = os.getenv("LINKEDIN_AUTHOR_URN", "urn:li:organization:12345678")


@lru_cache()
def get_settings() -> Settings:
    """Return cached singleton instance of application settings."""
    return Settings()
