"""Discord Webhook API integration adapter."""

import logging
from typing import Optional
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

    def mock_post(self, message: str, cta_url: str) -> PlatformResult:
        """Simulate posting when MOCK_MODE=True without fabricating live URLs."""
        simulated_preview = "https://discord.com/channels/mock_guild/mock_channel/simulated_post"
        logger.info("Discord: Executed in simulated mock mode.")
        return self.mock_result(simulated_preview, public_access=True)

    async def post(self, message: str, cta_url: str) -> PlatformResult:
        """Publish message via Discord Webhook."""
        if self.settings.mock_mode:
            return self.mock_post(message, cta_url)

        if not self.is_configured():
            logger.warning("Discord webhook URL is not configured.")
            return self.failure_result("Discord webhook URL is not configured (DISCORD_WEBHOOK_URL required)")

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
                msg_id = data.get("id")
                channel_id = data.get("channel_id")

                # Derive URL ONLY if real message ID and channel ID were returned by Discord
                posted_url: Optional[str] = None
                if msg_id and channel_id:
                    posted_url = f"https://discord.com/channels/@me/{channel_id}/{msg_id}"

                return self.success_result(posted_url=posted_url, public_access=True)

            elif response.status_code == 429:
                return self.failure_result("HTTP 429: Discord rate limit exceeded")
            elif response.status_code in (401, 404):
                return self.failure_result(f"HTTP {response.status_code}: Invalid or revoked Discord webhook URL")
            else:
                error_detail = response.text
                logger.error("Discord Webhook error: %s (status %d)", error_detail, response.status_code)
                return self.failure_result(f"HTTP {response.status_code}: {error_detail}")

        except httpx.TimeoutException:
            logger.error("Discord API request timed out.")
            return self.failure_result("Request timeout to Discord Webhook gateway")
        except httpx.RequestError as exc:
            logger.error("Discord connection error: %s", exc)
            return self.failure_result(f"Network error: {str(exc)}")
        except Exception as exc:
            logger.error("Discord unexpected error: %s", exc)
            return self.failure_result(f"Unexpected error: {str(exc)}")
