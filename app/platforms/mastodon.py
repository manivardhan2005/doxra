"""Mastodon Decentralized Social Network REST API adapter."""

import logging
from typing import Optional
import httpx

from app.config import Settings
from app.platforms.base import BasePlatform
from app.schemas import PlatformResult

logger = logging.getLogger(__name__)


class MastodonPlatform(BasePlatform):
    """
    Adapter for Mastodon REST API.
    Docs: https://docs.joinmastodon.org/methods/statuses/#create
    Endpoint: POST https://{instance}/api/v1/statuses
    """

    platform_name = "Mastodon"
    is_public = True

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.instance_url = settings.mastodon_instance_url
        self.access_token = settings.mastodon_access_token
        self.username = settings.mastodon_username.lstrip("@")

    def is_configured(self) -> bool:
        return bool(self.access_token and self.instance_url)

    def mock_post(self, message: str, cta_url: str) -> PlatformResult:
        """Simulate posting when MOCK_MODE=True without fabricating live URLs."""
        simulated_preview = f"{self.instance_url}/@{self.username}/simulated_status"
        logger.info("Mastodon: Executed in simulated mock mode.")
        return self.mock_result(simulated_preview, public_access=True)

    async def post(self, message: str, cta_url: str) -> PlatformResult:
        """Publish status update to Mastodon federated network."""
        if self.settings.mock_mode:
            return self.mock_post(message, cta_url)

        if not self.is_configured():
            logger.warning("Mastodon credentials not configured.")
            return self.failure_result("Mastodon credentials not configured (MASTODON_ACCESS_TOKEN and MASTODON_INSTANCE_URL required)")

        endpoint = f"{self.instance_url}/api/v1/statuses"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "status": message,
            "visibility": "public",
        }

        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
                response = await client.post(endpoint, headers=headers, json=payload)

            if response.status_code in (200, 201):
                data = response.json()
                status_id = data.get("id")
                
                # Derive URL only if genuine status was created
                posted_url: Optional[str] = data.get("url")
                if not posted_url and status_id:
                    posted_url = f"{self.instance_url}/@{self.username}/{status_id}"

                return self.success_result(posted_url=posted_url, public_access=True)

            elif response.status_code == 429:
                return self.failure_result("HTTP 429: Mastodon API rate limit exceeded")
            elif response.status_code in (401, 403):
                return self.failure_result(f"HTTP {response.status_code}: Invalid or unauthorized Mastodon access token")
            else:
                error_detail = response.text
                logger.error("Mastodon API error: %s (status %d)", error_detail, response.status_code)
                return self.failure_result(f"HTTP {response.status_code}: {error_detail}")

        except httpx.TimeoutException:
            logger.error("Mastodon API request timed out.")
            return self.failure_result("Request timeout to Mastodon API gateway")
        except httpx.RequestError as exc:
            logger.error("Mastodon connection error: %s", exc)
            return self.failure_result(f"Network error: {str(exc)}")
        except Exception as exc:
            logger.error("Mastodon unexpected error: %s", exc)
            return self.failure_result(f"Unexpected error: {str(exc)}")
