"""Orchestration service for asynchronous concurrent multi-platform posting."""

import asyncio
import logging
from typing import List

from app.config import Settings
from app.platforms.base import BasePlatform
from app.platforms.discord import DiscordPlatform
from app.platforms.linkedin import LinkedInPlatform
from app.platforms.mastodon import MastodonPlatform
from app.platforms.slack import SlackPlatform
from app.platforms.telegram import TelegramPlatform
from app.platforms.twitter import TwitterPlatform
from app.schemas import PlatformResult, PostingResponse
from app.utils.validators import validate_posting_message

logger = logging.getLogger(__name__)


class PostingService:
    """Coordinates concurrent publication across all supported social and messaging platforms."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        # Register all supported platform adapters (6 platforms >= 5 requirement)
        self.platforms: List[BasePlatform] = [
            TelegramPlatform(settings),
            DiscordPlatform(settings),
            SlackPlatform(settings),
            TwitterPlatform(settings),
            MastodonPlatform(settings),
            LinkedInPlatform(settings),
        ]

    async def _safe_post_to_platform(self, platform: BasePlatform, message: str, cta_url: str) -> PlatformResult:
        """Call a single platform's post method with top-level error isolation."""
        try:
            return await platform.post(message=message, cta_url=cta_url)
        except Exception as exc:
            logger.exception("Unhandled exception in platform %s: %s", platform.platform_name, exc)
            return platform.failure_result(f"Internal adapter error: {str(exc)}")

    async def broadcast_message(self, message: str) -> PostingResponse:
        """
        Validate input message, extract CTA link, and broadcast to all platforms concurrently.
        Ensures strict fault isolation: failure in one platform never blocks or degrades others.
        """
        # Validate rules and extract the single CTA link
        cta_url = validate_posting_message(message)

        logger.info(
            "Initiating broadcast across %d platforms for message: '%s...' (CTA: %s)",
            len(self.platforms),
            message[:40],
            cta_url,
        )

        # Launch concurrent async tasks for all platforms
        tasks = [
            self._safe_post_to_platform(platform, message, cta_url)
            for platform in self.platforms
        ]

        # Gather all platform results concurrently
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        final_results: List[PlatformResult] = []
        for idx, result in enumerate(raw_results):
            if isinstance(result, Exception):
                platform_name = self.platforms[idx].platform_name
                logger.error("Platform %s raised uncaught exception: %s", platform_name, result)
                final_results.append(
                    PlatformResult(
                        platform=platform_name,
                        status="failed",
                        posted_url=None,
                        public_access=False,
                        date=None,
                        time=None,
                        error=f"Uncaught task error: {str(result)}",
                    )
                )
            elif isinstance(result, PlatformResult):
                final_results.append(result)
            else:
                platform_name = self.platforms[idx].platform_name
                final_results.append(
                    PlatformResult(
                        platform=platform_name,
                        status="failed",
                        posted_url=None,
                        public_access=False,
                        date=None,
                        time=None,
                        error="Unknown result format returned",
                    )
                )

        # Calculate metrics
        successful_count = sum(1 for r in final_results if r.status == "success")
        failed_count = sum(1 for r in final_results if r.status == "failed")
        overall_success = successful_count > 0

        logger.info(
            "Broadcast finished: %d succeeded, %d failed out of %d total platforms",
            successful_count,
            failed_count,
            len(final_results),
        )

        return PostingResponse(
            success=overall_success,
            total_platforms=len(final_results),
            successful_posts=successful_count,
            failed_posts=failed_count,
            results=final_results,
        )
