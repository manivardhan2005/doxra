"""Unit and integration tests for the Automated Multi-Platform Posting System."""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.platforms.base import BasePlatform
from app.schemas import PlatformResult

client = TestClient(app)


def test_root_endpoint():
    """Verify root endpoint returns system metadata and supported platforms."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["posting_endpoint"] == "POST /posting"
    assert len(data["supported_platforms"]) >= 5


def test_health_check_endpoint():
    """Verify health endpoint reports system status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["platforms_supported"] >= 5


def test_openapi_schema_endpoint():
    """Verify OpenAPI documentation endpoint is reachable and describes /posting."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "/posting" in schema["paths"]
    assert "post" in schema["paths"]["/posting"]


def test_successful_multi_platform_posting():
    """Verify posting a valid message succeeds across all registered platforms."""
    payload = {
        "message": "Check out our latest business platform and grow your online visibility. https://example.com"
    }
    response = client.post("/posting", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["total_platforms"] >= 5
    assert data["successful_posts"] == data["total_platforms"]
    assert data["failed_posts"] == 0
    assert len(data["results"]) >= 5

    # Check each platform result fields
    platform_names = set()
    for result in data["results"]:
        assert result["status"] == "success"
        assert result["posted_url"] is not None
        assert result["posted_url"].startswith("http")
        assert result["date"] is not None
        assert result["time"] is not None
        assert result["error"] is None
        assert isinstance(result["public_access"], bool)
        platform_names.add(result["platform"])

    expected_platforms = {"Telegram", "Discord", "Slack", "X (Twitter)", "Mastodon", "LinkedIn"}
    assert expected_platforms.issubset(platform_names)


def test_validation_error_message_too_long():
    """Verify messages exceeding 200 characters are rejected with HTTP 422."""
    long_msg = "A" * 195 + " https://example.com"
    payload = {"message": long_msg}
    response = client.post("/posting", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert "200 characters" in data["detail"]


def test_validation_error_missing_cta_link():
    """Verify messages without any CTA link are rejected with HTTP 422."""
    payload = {"message": "Check out our latest business platform and grow your online visibility."}
    response = client.post("/posting", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert "Message must include exactly one Call-to-Action (CTA) link. None was found." in data["detail"]


def test_validation_error_multiple_cta_links():
    """Verify messages containing more than one CTA link are rejected with HTTP 422."""
    payload = {
        "message": "Visit our home https://example.com and our blog https://blog.example.com now!"
    }
    response = client.post("/posting", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert "Found 2 links" in data["detail"]


def test_validation_error_invalid_url_scheme():
    """Verify non-HTTP/HTTPS URLs are rejected."""
    payload = {"message": "Download our file ftp://files.example.com/app now"}
    response = client.post("/posting", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert "None was found" in data["detail"] or "Invalid URL scheme" in data["detail"]


def test_validation_error_ssrf_localhost():
    """Verify internal localhost/loopback addresses are blocked to prevent SSRF."""
    payload = {"message": "Internal service announcement http://localhost:8080/admin"}
    response = client.post("/posting", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert "SSRF protection" in data["detail"]


def test_validation_error_ssrf_private_ip():
    """Verify private IP addresses (127.0.0.1, 10.x.x.x, 192.168.x.x) are blocked."""
    payload = {"message": "Check our internal dashboard http://192.168.1.1/router"}
    response = client.post("/posting", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert "SSRF protection" in data["detail"]


def test_platform_failure_isolation():
    """
    Verify that if one platform fails (e.g. Discord encounters an error),
    the other platforms continue unaffected, and the response reflects the failure.
    """
    from app.main import posting_service

    # Find Discord platform in posting_service
    discord_platform = next(p for p in posting_service.platforms if p.platform_name == "Discord")

    # Mock Discord to return a failure
    mock_discord_failure = PlatformResult(
        platform="Discord",
        status="failed",
        posted_url=None,
        public_access=False,
        date=None,
        time=None,
        error="HTTP 401: Unauthorized webhook token",
    )

    with patch.object(discord_platform, "post", new_callable=AsyncMock) as mocked_post:
        mocked_post.return_value = mock_discord_failure

        payload = {
            "message": "Special discount for all platform subscribers! https://dxoratech.com/promo"
        }
        response = client.post("/posting", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True  # Other platforms succeeded
        assert data["failed_posts"] == 1
        assert data["successful_posts"] == data["total_platforms"] - 1

        discord_result = next(r for r in data["results"] if r["platform"] == "Discord")
        assert discord_result["status"] == "failed"
        assert discord_result["error"] == "HTTP 401: Unauthorized webhook token"
        assert discord_result["posted_url"] is None

        # Verify other platforms succeeded
        telegram_result = next(r for r in data["results"] if r["platform"] == "Telegram")
        assert telegram_result["status"] == "success"
        assert telegram_result["posted_url"] is not None


def test_all_platforms_failure_handling():
    """Verify graceful response when all platforms encounter errors."""
    from app.main import posting_service

    patches = []
    for platform in posting_service.platforms:
        p = patch.object(
            platform,
            "post",
            new_callable=AsyncMock,
            return_value=platform.failure_result("Connection timeout to API gateway"),
        )
        patches.append(p)
        p.start()

    try:
        payload = {"message": "Testing total outage resilience https://example.com/status"}
        response = client.post("/posting", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is False
        assert data["successful_posts"] == 0
        assert data["failed_posts"] == data["total_platforms"]
        for result in data["results"]:
            assert result["status"] == "failed"
            assert result["error"] == "Connection timeout to API gateway"
    finally:
        for p in patches:
            p.stop()
