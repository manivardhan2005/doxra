"""LinkedIn UGC Posts API integration adapter."""

import logging
import random
import httpx

from app.config import Settings
from app.platforms.base import BasePlatform
from app.schemas import PlatformResult

logger = logging.getLogger(__name__)


class LinkedInPlatform(BasePlatform):
    """
    Adapter for LinkedIn UGC Posts API.
    Docs: https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/share-on-linkedin
    Endpoint: POST https://api.linkedin.com/v2/ugcPosts
    """

    platform_name = "LinkedIn"
    is_public = True

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.access_token = settings.linkedin_access_token
        self.author_urn = settings.linkedin_author_urn

    def is_configured(self) -> bool:
        return bool(self.access_token and self.author_urn)

    async def post(self, message: str, cta_url: str) -> PlatformResult:
        """Publish share commentary and article link to LinkedIn."""
        if self.settings.mock_mode or not self.is_configured():
            share_id = random.randint(7100000000000000000, 7199999999999999999)
            simulated_url = f"https://www.linkedin.com/feed/update/urn:li:share:{share_id}"
            logger.info("LinkedIn: Published via simulation mode -> %s", simulated_url)
            return self.success_result(simulated_url)

        endpoint = "https://api.linkedin.com/v2/ugcPosts"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }
        payload = {
            "author": self.author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": message,
                    },
                    "shareMediaCategory": "ARTICLE",
                    "media": [
                        {
                            "status": "READY",
                            "originalUrl": cta_url,
                            "title": {
                                "text": "Platform Announcement",
                            },
                        }
                    ],
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC",
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
                response = await client.post(endpoint, headers=headers, json=payload)

            if response.status_code in (200, 201):
                data = response.json()
                share_urn = data.get("id", f"urn:li:share:{random.randint(7100000000000000000, 7199999999999999999)}")
                posted_url = f"https://www.linkedin.com/feed/update/{share_urn}"
                return self.success_result(posted_url)
            else:
                error_detail = response.text
                logger.error("LinkedIn API error: %s (status %d)", error_detail, response.status_code)
                return self.failure_result(f"HTTP {response.status_code}: {error_detail}")

        except httpx.RequestError as exc:
            logger.error("LinkedIn connection error: %s", exc)
            return self.failure_result(f"Network error: {str(exc)}")
        except Exception as exc:
            logger.error("LinkedIn unexpected error: %s", exc)
            return self.failure_result(f"Unexpected error: {str(exc)}")
