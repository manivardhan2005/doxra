"""Slack Incoming Webhook integration adapter."""

import logging
from typing import Optional
import httpx

from app.config import Settings
from app.platforms.base import BasePlatform
from app.schemas import PlatformResult

logger = logging.getLogger(__name__)


class SlackPlatform(BasePlatform):
    """
    Adapter for Slack Incoming Webhooks.
    Docs: https://api.slack.com/messaging/webhooks
    Endpoint: POST https://hooks.slack.com/services/...
    Note: Slack Incoming Webhooks broadcast to internal channels and return 'ok' without public permalinks.
    """

    platform_name = "Slack"
    # Slack channels are private / team-internal by default
    is_public = False

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.webhook_url = settings.slack_webhook_url

    def is_configured(self) -> bool:
        return bool(self.webhook_url and self.webhook_url.startswith("https://hooks.slack.com/services/"))

    def mock_post(self, message: str, cta_url: str) -> PlatformResult:
        """Simulate posting when MOCK_MODE=True without fabricating live URLs."""
        simulated_preview = "https://app.slack.com/client/mock_workspace/mock_channel"
        logger.info("Slack: Executed in simulated mock mode.")
        return self.mock_result(simulated_preview, public_access=False)

    async def post(self, message: str, cta_url: str) -> PlatformResult:
        """Publish message via Slack Incoming Webhook."""
        if self.settings.mock_mode:
            return self.mock_post(message, cta_url)

        if not self.is_configured():
            logger.warning("Slack webhook URL is not configured.")
            return self.failure_result("Slack webhook URL is not configured (SLACK_WEBHOOK_URL required)")

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
                # Slack Incoming Webhooks acknowledge publication with 'ok' but do not provide permalinks.
                # In accordance with API specs, we return success with posted_url=None rather than a fabricated URL.
                return self.success_result(posted_url=None, public_access=False)

            elif response.status_code == 429:
                return self.failure_result("HTTP 429: Slack API rate limit exceeded")
            elif response.status_code in (403, 404):
                return self.failure_result(f"HTTP {response.status_code}: Invalid or revoked Slack webhook URL ({response.text.strip()})")
            else:
                error_detail = response.text
                logger.error("Slack Webhook error: %s (status %d)", error_detail, response.status_code)
                return self.failure_result(f"HTTP {response.status_code}: {error_detail}")

        except httpx.TimeoutException:
            logger.error("Slack API request timed out.")
            return self.failure_result("Request timeout to Slack Webhook gateway")
        except httpx.RequestError as exc:
            logger.error("Slack connection error: %s", exc)
            return self.failure_result(f"Network error: {str(exc)}")
        except Exception as exc:
            logger.error("Slack unexpected error: %s", exc)
            return self.failure_result(f"Unexpected error: {str(exc)}")
