"""Base class and common contracts for multi-platform adapters."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional, Tuple

from app.schemas import PlatformResult


class BasePlatform(ABC):
    """Abstract base class that all platform adapters must implement."""

    platform_name: str = "BasePlatform"
    is_public: bool = True

    def get_current_timestamp(self) -> Tuple[str, str]:
        """Return current date (YYYY-MM-DD) and time (HH:MM:SS) in UTC."""
        now = datetime.now(timezone.utc)
        return now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")

    def success_result(
        self,
        posted_url: Optional[str],
        public_access: Optional[bool] = None,
    ) -> PlatformResult:
        """Helper to build a standardized successful live PlatformResult."""
        date_str, time_str = self.get_current_timestamp()
        pub = self.is_public if public_access is None else public_access
        return PlatformResult(
            platform=self.platform_name,
            status="success",
            is_mock=False,
            posted_url=posted_url,
            public_access=pub,
            date=date_str,
            time=time_str,
            error=None,
        )

    def mock_result(
        self,
        simulated_url: Optional[str],
        public_access: Optional[bool] = None,
    ) -> PlatformResult:
        """Helper to build an explicit simulated result when MOCK_MODE is enabled."""
        date_str, time_str = self.get_current_timestamp()
        pub = self.is_public if public_access is None else public_access
        return PlatformResult(
            platform=self.platform_name,
            status="simulated",
            is_mock=True,
            posted_url=simulated_url,
            public_access=pub,
            date=date_str,
            time=time_str,
            error=None,
        )

    def failure_result(self, error_message: str) -> PlatformResult:
        """Helper to build a standardized failed PlatformResult."""
        return PlatformResult(
            platform=self.platform_name,
            status="failed",
            is_mock=False,
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
    def mock_post(self, message: str, cta_url: str) -> PlatformResult:
        """Execute simulated posting when MOCK_MODE=True."""
        pass

    @abstractmethod
    async def post(self, message: str, cta_url: str) -> PlatformResult:
        """
        Execute publication of message and CTA link to the platform.
        Enforces strict separation:
          1. if mock_mode -> calls mock_post()
          2. if not is_configured() -> returns failure_result('Platform credentials are not configured')
          3. otherwise -> makes live API call with real credentials.
        """
        pass
