"""Mastodon Decentralized Social Network REST API adapter."""

import logging
import random
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

    async def post(self, message: str, cta_url: str) -> PlatformResult:
        """Publish status update to Mastodon federated network."""
        if self.settings.mock_mode or not self.is_configured():
            status_id = random.randint(110000000000000000, 119999999999999999)
            simulated_url = f"{self.instance_url}/@{self.username}/{status_id}"
            logger.info("Mastodon: Published via simulation mode -> %s", simulated_url)
            return self.success_result(simulated_url)

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
                posted_url = data.get("url") or f"{self.instance_url}/@{self.username}/{data.get('id')}"
                return self.success_result(posted_url)
            else:
                error_detail = response.text
                logger.error("Mastodon API error: %s (status %d)", error_detail, response.status_code)
                return self.failure_result(f"HTTP {response.status_code}: {error_detail}")

        except httpx.RequestError as exc:
            logger.error("Mastodon connection error: %s", exc)
            return self.failure_result(f"Network error: {str(exc)}")
        except Exception as exc:
            logger.error("Mastodon unexpected error: %s", exc)
            return self.failure_result(f"Unexpected error: {str(exc)}")
