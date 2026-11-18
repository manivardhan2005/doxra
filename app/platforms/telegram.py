"""Telegram Bot API integration adapter."""

import logging
from typing import Optional
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

    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def mock_post(self, message: str, cta_url: str) -> PlatformResult:
        """Simulate posting when MOCK_MODE=True without fabricating live URLs."""
        simulated_preview = "https://t.me/dxoratech_preview/simulated-post"
        logger.info("Telegram: Executed in simulated mock mode.")
        return self.mock_result(simulated_preview, public_access=True)

    async def post(self, message: str, cta_url: str) -> PlatformResult:
        """Publish message to Telegram channel/chat."""
        # 1. Check Mock Mode
        if self.settings.mock_mode:
            return self.mock_post(message, cta_url)

        # 2. Check Configuration (Do not simulate if live mode is requested without credentials)
        if not self.is_configured():
            logger.warning("Telegram credentials not configured.")
            return self.failure_result("Telegram credentials not configured (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID required)")

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
                msg_id = data.get("result", {}).get("message_id")
                
                # Derive realistic URL only if actual message ID exists
                posted_url: Optional[str] = None
                public_access = False

                if msg_id:
                    if self.chat_id.startswith("@"):
                        # Public channel with username
                        posted_url = f"https://t.me/{self.chat_id.lstrip('@')}/{msg_id}"
                        public_access = True
                    elif self.chat_id.startswith("-100"):
                        # Private supergroup/channel permalink (requires member login)
                        clean_id = self.chat_id[4:]
                        posted_url = f"https://t.me/c/{clean_id}/{msg_id}"
                        public_access = False
                    else:
                        # Direct user chat has no public web permalink
                        posted_url = None
                        public_access = False

                return self.success_result(posted_url=posted_url, public_access=public_access)

            elif response.status_code == 429:
                return self.failure_result("HTTP 429: Telegram API rate limit exceeded")
            elif response.status_code in (401, 403):
                return self.failure_result("HTTP 401/403: Invalid bot token or bot lacks permission in target chat")
            else:
                error_detail = response.text
                logger.error("Telegram API error: %s (status %d)", error_detail, response.status_code)
                return self.failure_result(f"HTTP {response.status_code}: {error_detail}")

        except httpx.TimeoutException:
            logger.error("Telegram API request timed out.")
            return self.failure_result("Request timeout to Telegram API gateway")
        except httpx.RequestError as exc:
            logger.error("Telegram request connection error: %s", exc)
            return self.failure_result(f"Network error: {str(exc)}")
        except Exception as exc:
            logger.error("Telegram unexpected error: %s", exc)
            return self.failure_result(f"Unexpected error: {str(exc)}")
