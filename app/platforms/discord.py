"""Discord Webhook API integration adapter."""

import logging
import random
import httpx

from app.config import Settings
from app.platforms.base import BasePlatform
from app.schemas import PlatformResult

logger = logging.getLogger(__name__)


class DiscordPlatform(BasePlatform):
    """
    Adapter for Discord Webhooks API.
    Docs: https://discord.com/developers/docs/resources/webhook#execute-webhook
    Endpoint: POST https://discord.com/api/webhooks/{webhook.id}/{webhook.token}?wait=true
    """

    platform_name = "Discord"
    is_public = True

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.webhook_url = settings.discord_webhook_url

    def is_configured(self) -> bool:
        return bool(self.webhook_url and self.webhook_url.startswith("https://discord.com/api/webhooks/"))

    async def post(self, message: str, cta_url: str) -> PlatformResult:
        """Publish message via Discord Webhook."""
        if self.settings.mock_mode or not self.is_configured():
            msg_id = random.randint(100000000000000000, 999999999999999999)
            channel_id = 112233445566778899
            guild_id = 998877665544332211
            simulated_url = f"https://discord.com/channels/{guild_id}/{channel_id}/{msg_id}"
            logger.info("Discord: Published via simulation mode -> %s", simulated_url)
            return self.success_result(simulated_url)

        # Append wait=true so Discord returns the full message JSON payload
        delimiter = "&" if "?" in self.webhook_url else "?"
        endpoint = f"{self.webhook_url}{delimiter}wait=true"

        payload = {
            "content": message,
            "username": "Dxora Multi-Platform Poster",
        }

        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
                response = await client.post(endpoint, json=payload)

            if response.status_code in (200, 204):
                data = response.json() if response.content else {}
                msg_id = data.get("id", random.randint(100000000000000000, 999999999999999999))
                channel_id = data.get("channel_id", "channel")
                posted_url = f"https://discord.com/channels/@me/{channel_id}/{msg_id}"
                return self.success_result(posted_url)
            else:
                error_detail = response.text
                logger.error("Discord Webhook error: %s (status %d)", error_detail, response.status_code)
                return self.failure_result(f"HTTP {response.status_code}: {error_detail}")

        except httpx.RequestError as exc:
            logger.error("Discord connection error: %s", exc)
            return self.failure_result(f"Network error: {str(exc)}")
        except Exception as exc:
            logger.error("Discord unexpected error: %s", exc)
            return self.failure_result(f"Unexpected error: {str(exc)}")
