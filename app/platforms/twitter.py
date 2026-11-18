"""X (formerly Twitter) API v2 integration adapter."""

import logging
import random
import httpx

from app.config import Settings
from app.platforms.base import BasePlatform
from app.schemas import PlatformResult

logger = logging.getLogger(__name__)


class TwitterPlatform(BasePlatform):
    """
    Adapter for X (Twitter) API v2.
    Docs: https://developer.x.com/en/docs/twitter-api/tweets/manage-tweets/api-reference/post-tweets
    Endpoint: POST https://api.twitter.com/2/tweets
    """

    platform_name = "X (Twitter)"
    is_public = True

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.bearer_token = settings.twitter_bearer_token
        self.username = settings.twitter_username.lstrip("@")

    def is_configured(self) -> bool:
        return bool(self.bearer_token)

    async def post(self, message: str, cta_url: str) -> PlatformResult:
        """Publish tweet via X (Twitter) API v2."""
        if self.settings.mock_mode or not self.is_configured():
            tweet_id = random.randint(1800000000000000000, 1899999999999999999)
            simulated_url = f"https://x.com/{self.username}/status/{tweet_id}"
            logger.info("X (Twitter): Published via simulation mode -> %s", simulated_url)
            return self.success_result(simulated_url)

        endpoint = "https://api.twitter.com/2/tweets"
        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
        }
        payload = {"text": message}

        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
                response = await client.post(endpoint, headers=headers, json=payload)

            if response.status_code in (200, 201):
                data = response.json()
                tweet_id = data.get("data", {}).get("id", random.randint(1800000000000000000, 1899999999999999999))
                posted_url = f"https://x.com/{self.username}/status/{tweet_id}"
                return self.success_result(posted_url)
            else:
                error_detail = response.text
                logger.error("X (Twitter) API error: %s (status %d)", error_detail, response.status_code)
                return self.failure_result(f"HTTP {response.status_code}: {error_detail}")

        except httpx.RequestError as exc:
            logger.error("X (Twitter) connection error: %s", exc)
            return self.failure_result(f"Network error: {str(exc)}")
        except Exception as exc:
            logger.error("X (Twitter) unexpected error: %s", exc)
            return self.failure_result(f"Unexpected error: {str(exc)}")
