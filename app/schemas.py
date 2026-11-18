"""Pydantic schemas for request and response models."""

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

from app.utils.validators import validate_posting_message


class PostingRequest(BaseModel):
    """Request payload for multi-platform posting."""

    message: str = Field(
        ...,
        max_length=200,
        description="The content to be posted across platforms (max 200 chars, exactly 1 CTA link).",
        examples=[
            "Check out our latest business platform and grow your online visibility. https://example.com"
        ],
    )

    @field_validator("message")
    @classmethod
    def validate_message_rules(cls, v: str) -> str:
        """Validate character count, CTA link requirement, and URL safety."""
        validate_posting_message(v)
        return v


class PlatformResult(BaseModel):
    """Result details of posting to a single platform."""

    platform: str = Field(..., description="Platform name", examples=["Telegram", "Discord"])
    status: str = Field(
        ...,
        description="Posting status: 'success' (live published), 'simulated' (mock mode), or 'failed'",
        examples=["success", "simulated", "failed"],
    )
    is_mock: bool = Field(
        False,
        description="Explicit flag indicating whether this operation was executed in simulated/mock mode",
    )
    posted_url: Optional[str] = Field(
        None,
        description="Direct URL of the published post derived from platform response, or null if unavailable",
        examples=["https://t.me/dxoratech/102"],
    )
    public_access: bool = Field(
        False,
        description="Whether the posted content is publicly viewable without authentication",
    )
    date: Optional[str] = Field(
        None,
        description="Date of posting in YYYY-MM-DD format (UTC)",
        examples=["2026-11-18"],
    )
    time: Optional[str] = Field(
        None,
        description="Time of posting in HH:MM:SS format (UTC)",
        examples=["11:30:00"],
    )
    error: Optional[str] = Field(
        None,
        description="Error details if posting failed",
        examples=[None, "Platform credentials are not configured"],
    )


class PostingResponse(BaseModel):
    """API response summarizing execution across all platforms."""

    success: bool = Field(..., description="Overall status indicating if at least one platform succeeded or simulated")
    mock_mode: bool = Field(False, description="Whether the request was processed in mock/simulation mode")
    total_platforms: int = Field(..., description="Total number of platforms targeted")
    successful_posts: int = Field(..., description="Count of successfully published or simulated platforms")
    failed_posts: int = Field(..., description="Count of failed platform publications")
    results: List[PlatformResult] = Field(..., description="Detailed list of results for each platform")


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str
    app: str
    version: str
    platforms_supported: int
    mock_mode: bool
