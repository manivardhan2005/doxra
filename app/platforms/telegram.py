"""Telegram Bot API integration adapter."""

import logging
import random
import httpx

from app.config import Settings
from app.platforms.base import BasePlatform
from app.schemas import PlatformResult

logger = logging.getLogger(__name__)


class TelegramPlatform(BasePlatform):
    """
    Adapter for Telegram Bot API.
    Docs: https://core.telegram.org/bots/api#sendmessage
    Endpoint: POST https://api.telegram.org/bot<token>/sendMessage
    """

    platform_name = "Telegram"
    is_public = True

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.bot_token = settings.telegram_bot_token
        self.chat_id = settings.telegram_chat_id
        self.channel_username = settings.telegram_channel_username

    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    async def post(self, message: str, cta_url: str) -> PlatformResult:
        """Publish message to Telegram channel/chat."""
        # Simulated mode if mock_mode is on or credentials not provided
        if self.settings.mock_mode or not self.is_configured():
            msg_id = random.randint(1000, 99999)
            channel = self.channel_username.lstrip("@")
            simulated_url = f"https://t.me/{channel}/{msg_id}"
            logger.info("Telegram: Published via simulation mode -> %s", simulated_url)
            return self.success_result(simulated_url)

        endpoint = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "disable_web_page_preview": False,
        }

        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
                response = await client.post(endpoint, json=payload)

            if response.status_code == 200:
                data = response.json()
                msg_id = data.get("result", {}).get("message_id", random.randint(1000, 99999))
                channel = self.channel_username.lstrip("@")
                posted_url = f"https://t.me/{channel}/{msg_id}"
                return self.success_result(posted_url)
            else:
                error_detail = response.text
                logger.error("Telegram API error: %s (status %d)", error_detail, response.status_code)
                return self.failure_result(f"HTTP {response.status_code}: {error_detail}")

        except httpx.RequestError as exc:
            logger.error("Telegram request connection error: %s", exc)
            return self.failure_result(f"Network error: {str(exc)}")
        except Exception as exc:
            logger.error("Telegram unexpected error: %s", exc)
            return self.failure_result(f"Unexpected error: {str(exc)}")
