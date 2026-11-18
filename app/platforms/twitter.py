"""X (formerly Twitter) API v2 integration adapter with OAuth 1.0a and OAuth 2.0 User Context."""

import base64
import hashlib
import hmac
import logging
import time
from typing import Dict, Optional
import urllib.parse
import uuid
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
    Authentication: Requires User-Context credentials (OAuth 1.0a User Context or OAuth 2.0 with 'tweet.write' scope).
    """

    platform_name = "X (Twitter)"
    is_public = True

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.api_key = settings.twitter_api_key
        self.api_secret = settings.twitter_api_secret
        self.access_token = settings.twitter_access_token
        self.access_token_secret = settings.twitter_access_token_secret
        self.bearer_token = settings.twitter_bearer_token
        self.username = settings.twitter_username.lstrip("@")

    def is_configured(self) -> bool:
        """User-context authorization is required for /2/tweets creation."""
        has_oauth1 = bool(
            self.api_key
            and self.api_secret
            and self.access_token
            and self.access_token_secret
        )
        has_oauth2_user = bool(self.access_token or self.bearer_token)
        return has_oauth1 or has_oauth2_user

    def _generate_oauth1_header(self, url: str, method: str = "POST") -> str:
        """Generate standard RFC 5849 OAuth 1.0a User Context Authorization header."""
        oauth_params: Dict[str, str] = {
            "oauth_consumer_key": self.api_key or "",
            "oauth_nonce": uuid.uuid4().hex,
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": str(int(time.time())),
            "oauth_token": self.access_token or "",
            "oauth_version": "1.0",
        }

        # Normalize parameters in lexicographical order
        param_string = "&".join(
            f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(oauth_params[k], safe='')}"
            for k in sorted(oauth_params.keys())
        )

        # Build signature base string
        base_string = "&".join(
            [
                method.upper(),
                urllib.parse.quote(url, safe=""),
                urllib.parse.quote(param_string, safe=""),
            ]
        )

        # Signing key = consumer_secret & token_secret
        signing_key = (
            f"{urllib.parse.quote(self.api_secret or '', safe='')}&"
            f"{urllib.parse.quote(self.access_token_secret or '', safe='')}"
        )

        # Compute HMAC-SHA1 signature
        raw_sig = hmac.new(
            signing_key.encode("utf-8"),
            base_string.encode("utf-8"),
            hashlib.sha1,
        ).digest()
        oauth_params["oauth_signature"] = base64.b64encode(raw_sig).decode("utf-8")

        # Format Authorization header string
        header_parts = [
            f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(v, safe="")}"'
            for k, v in sorted(oauth_params.items())
        ]
        return "OAuth " + ", ".join(header_parts)

    def mock_post(self, message: str, cta_url: str) -> PlatformResult:
        """Simulate posting when MOCK_MODE=True without fabricating live URLs."""
        simulated_preview = f"https://x.com/{self.username}/status/simulated_tweet"
        logger.info("X (Twitter): Executed in simulated mock mode.")
        return self.mock_result(simulated_preview, public_access=True)

    async def post(self, message: str, cta_url: str) -> PlatformResult:
        """Publish tweet via X (Twitter) API v2 using user-context authentication."""
        if self.settings.mock_mode:
            return self.mock_post(message, cta_url)

        if not self.is_configured():
            logger.warning("X (Twitter) user-context credentials not configured.")
            return self.failure_result(
                "X (Twitter) user-context credentials not configured (OAuth 1.0a keys or OAuth 2.0 User Token required)"
            )

        endpoint = "https://api.twitter.com/2/tweets"
        payload = {"text": message}

        # Select authentication method
        has_oauth1 = bool(
            self.api_key
            and self.api_secret
            and self.access_token
            and self.access_token_secret
        )

        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if has_oauth1:
            headers["Authorization"] = self._generate_oauth1_header(endpoint, "POST")
        else:
            token = self.access_token or self.bearer_token
            headers["Authorization"] = f"Bearer {token}"

        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
                response = await client.post(endpoint, headers=headers, json=payload)

            if response.status_code in (200, 201):
                data = response.json()
                tweet_id = data.get("data", {}).get("id")

                # Derive URL only if genuine tweet ID was returned by X
                posted_url: Optional[str] = None
                if tweet_id:
                    posted_url = f"https://x.com/{self.username}/status/{tweet_id}"

                return self.success_result(posted_url=posted_url, public_access=True)

            elif response.status_code == 429:
                return self.failure_result("HTTP 429: X (Twitter) API rate limit exceeded")
            elif response.status_code == 401:
                return self.failure_result("HTTP 401: Invalid or expired X (Twitter) OAuth credentials")
            elif response.status_code == 403:
                return self.failure_result(
                    "HTTP 403: Forbidden - Application lacks required 'tweet.write' user context permissions"
                )
            else:
                error_detail = response.text
                logger.error("X (Twitter) API error: %s (status %d)", error_detail, response.status_code)
                return self.failure_result(f"HTTP {response.status_code}: {error_detail}")

        except httpx.TimeoutException:
            logger.error("X (Twitter) API request timed out.")
            return self.failure_result("Request timeout to X (Twitter) API gateway")
        except httpx.RequestError as exc:
            logger.error("X (Twitter) connection error: %s", exc)
            return self.failure_result(f"Network error: {str(exc)}")
        except Exception as exc:
            logger.error("X (Twitter) unexpected error: %s", exc)
            return self.failure_result(f"Unexpected error: {str(exc)}")
