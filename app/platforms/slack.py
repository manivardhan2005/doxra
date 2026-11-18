"""Slack Incoming Webhook integration adapter."""

import logging
import time
import httpx

from app.config import Settings
from app.platforms.base import BasePlatform
from app.schemas import PlatformResult

logger = logging.getLogger(__name__)


class SlackPlatform(BasePlatform):
    """
    Adapter for Slack Incoming Webhooks.
    Docs: https://api.slack.com/messaging/webhooks
    Endpoint: POST https://hooks.slack.com/services/T.../B.../X...
    """

    platform_name = "Slack"
    # Slack workspaces are private / team-internal by default
    is_public = False

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.webhook_url = settings.slack_webhook_url

    def is_configured(self) -> bool:
        return bool(self.webhook_url and self.webhook_url.startswith("https://hooks.slack.com/services/"))

    async def post(self, message: str, cta_url: str) -> PlatformResult:
        """Publish message via Slack Incoming Webhook."""
        if self.settings.mock_mode or not self.is_configured():
            ts = f"{int(time.time())}.{int(time.time() * 1000) % 1000:03d}000"
            simulated_url = f"https://app.slack.com/client/T01234567/C09876543/thread/{ts}"
            logger.info("Slack: Published via simulation mode -> %s", simulated_url)
            return self.success_result(simulated_url)

        payload = {
            "text": message,
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": message,
                    },
                }
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
                response = await client.post(self.webhook_url, json=payload)

            if response.status_code == 200 and response.text.strip().lower() == "ok":
                ts = f"{int(time.time())}.000100"
                posted_url = f"https://app.slack.com/client/workspace/broadcast/{ts}"
                return self.success_result(posted_url)
            else:
                error_detail = response.text
                logger.error("Slack Webhook error: %s (status %d)", error_detail, response.status_code)
                return self.failure_result(f"HTTP {response.status_code}: {error_detail}")

        except httpx.RequestError as exc:
            logger.error("Slack connection error: %s", exc)
            return self.failure_result(f"Network error: {str(exc)}")
        except Exception as exc:
            logger.error("Slack unexpected error: %s", exc)
            return self.failure_result(f"Unexpected error: {str(exc)}")
