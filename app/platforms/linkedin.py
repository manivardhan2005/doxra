"""LinkedIn UGC Posts API integration adapter."""

import logging
from typing import Optional
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

    def mock_post(self, message: str, cta_url: str) -> PlatformResult:
        """Simulate posting when MOCK_MODE=True without fabricating live URLs."""
        simulated_preview = "https://www.linkedin.com/feed/update/urn:li:share:simulated_share"
        logger.info("LinkedIn: Executed in simulated mock mode.")
        return self.mock_result(simulated_preview, public_access=True)

    async def post(self, message: str, cta_url: str) -> PlatformResult:
        """Publish share commentary and article link to LinkedIn."""
        if self.settings.mock_mode:
            return self.mock_post(message, cta_url)

        if not self.is_configured():
            logger.warning("LinkedIn credentials not configured.")
            return self.failure_result("LinkedIn credentials not configured (LINKEDIN_ACCESS_TOKEN and LINKEDIN_AUTHOR_URN required)")

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
                share_urn = data.get("id")

                # Derive URL only if real share URN was provided by LinkedIn
                posted_url: Optional[str] = None
                if share_urn:
                    posted_url = f"https://www.linkedin.com/feed/update/{share_urn}"

                return self.success_result(posted_url=posted_url, public_access=True)

            elif response.status_code == 429:
                return self.failure_result("HTTP 429: LinkedIn API rate limit exceeded")
            elif response.status_code in (401, 403):
                return self.failure_result(f"HTTP {response.status_code}: Invalid or unauthorized LinkedIn OAuth token")
            else:
                error_detail = response.text
                logger.error("LinkedIn API error: %s (status %d)", error_detail, response.status_code)
                return self.failure_result(f"HTTP {response.status_code}: {error_detail}")

        except httpx.TimeoutException:
            logger.error("LinkedIn API request timed out.")
            return self.failure_result("Request timeout to LinkedIn API gateway")
        except httpx.RequestError as exc:
            logger.error("LinkedIn connection error: %s", exc)
            return self.failure_result(f"Network error: {str(exc)}")
        except Exception as exc:
            logger.error("LinkedIn unexpected error: %s", exc)
            return self.failure_result(f"Unexpected error: {str(exc)}")
