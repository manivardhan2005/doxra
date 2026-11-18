"""Base class and common contracts for multi-platform adapters."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Tuple

from app.schemas import PlatformResult


class BasePlatform(ABC):
    """Abstract base class that all platform adapters must implement."""

    platform_name: str = "BasePlatform"
    is_public: bool = True

    def get_current_timestamp(self) -> Tuple[str, str]:
        """Return current date (YYYY-MM-DD) and time (HH:MM:SS) in UTC."""
        now = datetime.now(timezone.utc)
        return now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")

    def success_result(self, posted_url: str) -> PlatformResult:
        """Helper to build a standardized successful PlatformResult."""
        date_str, time_str = self.get_current_timestamp()
        return PlatformResult(
            platform=self.platform_name,
            status="success",
            posted_url=posted_url,
            public_access=self.is_public,
            date=date_str,
            time=time_str,
            error=None,
        )

    def failure_result(self, error_message: str) -> PlatformResult:
        """Helper to build a standardized failed PlatformResult."""
        return PlatformResult(
            platform=self.platform_name,
            status="failed",
            posted_url=None,
            public_access=False,
            date=None,
            time=None,
            error=error_message,
        )

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if live credentials/configurations for this platform are present."""
        pass

    @abstractmethod
    async def post(self, message: str, cta_url: str) -> PlatformResult:
        """
        Execute publication of message and CTA link to the platform.
        Must handle its own exceptions internally and return a PlatformResult.
        """
        pass
