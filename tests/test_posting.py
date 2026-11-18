"""Comprehensive unit and integration test suite for Automated Multi-Platform Posting System."""

import socket
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app, posting_service
from app.platforms.base import BasePlatform
from app.schemas import PlatformResult

client = TestClient(app)


# ------------------------------------------------------------------------------
# 1. API Metadata & Health Tests
# ------------------------------------------------------------------------------

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


# ------------------------------------------------------------------------------
# 2. Mock Mode vs Live Mode Distinction Tests
# ------------------------------------------------------------------------------

def test_mock_mode_explicitly_identifies_simulated_results(monkeypatch):
    """
    Verify that when MOCK_MODE is enabled, results are explicitly flagged as
    simulated (is_mock=True, status='simulated') rather than pretending to be live posts.
    """
    monkeypatch.setattr(posting_service.settings, "mock_mode", True)
    for p in posting_service.platforms:
        monkeypatch.setattr(p.settings, "mock_mode", True)

    payload = {
        "message": "Promote your business online with Dxora Technologies. https://example.com"
    }
    response = client.post("/posting", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["mock_mode"] is True
    assert data["total_platforms"] >= 5

    for result in data["results"]:
        assert result["is_mock"] is True
        assert result["status"] == "simulated"
        assert result["date"] is not None
        assert result["time"] is not None
        assert result["error"] is None


def test_mock_mode_disabled_missing_credentials_fails(monkeypatch):
    """
    Verify that when MOCK_MODE is False, unconfigured platforms return
    status='failed' with a clear credentials error, rather than silently simulating success.
    """
    monkeypatch.setattr(posting_service.settings, "mock_mode", False)
    for p in posting_service.platforms:
        monkeypatch.setattr(p.settings, "mock_mode", False)
        monkeypatch.setattr(p, "is_configured", lambda: False)

    payload = {
        "message": "Testing unconfigured live platform failure https://example.com/test"
    }
    response = client.post("/posting", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is False
    assert data["successful_posts"] == 0
    assert data["failed_posts"] == data["total_platforms"]

    for result in data["results"]:
        assert result["status"] == "failed"
        assert result["is_mock"] is False
        assert "credentials" in result["error"].lower() or "not configured" in result["error"].lower()


# ------------------------------------------------------------------------------
# 3. Input Validation Tests
# ------------------------------------------------------------------------------

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
    """Verify non-HTTP/HTTPS URLs (e.g. ftp://) are rejected with HTTP 422."""
    payload = {"message": "Download our file ftp://files.example.com/app now"}
    response = client.post("/posting", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False


def test_validation_error_url_credentials_prohibited():
    """Verify embedded credentials in URLs (user:pass@host) are rejected for security."""
    payload = {"message": "Internal link http://admin:supersecret@example.com/login"}
    response = client.post("/posting", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert "Embedded credentials" in data["detail"]


# ------------------------------------------------------------------------------
# 4. SSRF Security Hardening Tests
# ------------------------------------------------------------------------------

def test_validation_error_ssrf_localhost():
    """Verify internal localhost/loopback addresses are blocked to prevent SSRF."""
    payload = {"message": "Internal service announcement http://localhost:8080/admin"}
    response = client.post("/posting", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert "SSRF protection" in data["detail"]


def test_validation_error_ssrf_private_ip():
    """Verify private IPv4 addresses (127.0.0.1, 10.x.x.x, 192.168.x.x) are blocked."""
    payload = {"message": "Check our internal dashboard http://192.168.1.1/router"}
    response = client.post("/posting", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert "SSRF protection" in data["detail"]


def test_validation_error_ssrf_ipv6_loopback_and_linklocal():
    """Verify IPv6 loopback (::1) and link-local (fe80::) addresses are blocked."""
    for bad_url in ("http://[::1]/test", "http://[fe80::1]/test", "http://[::ffff:127.0.0.1]/test"):
        payload = {"message": f"IPv6 announcement {bad_url}"}
        response = client.post("/posting", json=payload)
        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert "SSRF protection" in data["detail"]


def test_validation_error_dns_resolves_to_private_ip():
    """Verify domains that resolve via DNS to internal/private IPs are blocked (DNS rebinding protection)."""
    fake_dns_result = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 0))]
    with patch("socket.getaddrinfo", return_value=fake_dns_result):
        payload = {"message": "Visit our company portal https://rebound-internal.com/secure"}
        response = client.post("/posting", json=payload)
        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert "SSRF protection" in data["detail"]
        assert "10.0.0.5" in data["detail"]


# ------------------------------------------------------------------------------
# 5. Fault Isolation & API Status Handling Tests
# ------------------------------------------------------------------------------

def test_platform_failure_isolation(monkeypatch):
    """
    Verify that if one platform fails (e.g. Discord encounters an error),
    the other platforms continue unaffected, and the response reflects the failure.
    """
    monkeypatch.setattr(posting_service.settings, "mock_mode", True)
    for p in posting_service.platforms:
        monkeypatch.setattr(p.settings, "mock_mode", True)

    discord_platform = next(p for p in posting_service.platforms if p.platform_name == "Discord")

    mock_discord_failure = PlatformResult(
        platform="Discord",
        status="failed",
        is_mock=False,
        posted_url=None,
        public_access=False,
        date=None,
        time=None,
        error="HTTP 401: Unauthorized webhook token",
    )

    with patch.object(discord_platform, "post", new_callable=AsyncMock, return_value=mock_discord_failure):
        payload = {
            "message": "Special discount for all platform subscribers! https://dxoratech.com/promo"
        }
        response = client.post("/posting", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["failed_posts"] == 1
        assert data["successful_posts"] == data["total_platforms"] - 1

        discord_result = next(r for r in data["results"] if r["platform"] == "Discord")
        assert discord_result["status"] == "failed"
        assert discord_result["error"] == "HTTP 401: Unauthorized webhook token"
        assert discord_result["posted_url"] is None


def test_platform_rate_limit_429_captured(monkeypatch):
    """Verify HTTP 429 rate limit is captured properly without blocking other platforms."""
    monkeypatch.setattr(posting_service.settings, "mock_mode", True)
    for p in posting_service.platforms:
        monkeypatch.setattr(p.settings, "mock_mode", True)

    telegram_platform = next(p for p in posting_service.platforms if p.platform_name == "Telegram")

    mock_429 = PlatformResult(
        platform="Telegram",
        status="failed",
        is_mock=False,
        posted_url=None,
        public_access=False,
        date=None,
        time=None,
        error="HTTP 429: Telegram API rate limit exceeded",
    )

    with patch.object(telegram_platform, "post", new_callable=AsyncMock, return_value=mock_429):
        payload = {"message": "Rate limit test message https://example.com/deal"}
        response = client.post("/posting", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        tg_res = next(r for r in data["results"] if r["platform"] == "Telegram")
        assert tg_res["status"] == "failed"
        assert "rate limit exceeded" in tg_res["error"]


def test_platform_timeout_captured(monkeypatch):
    """Verify platform request timeouts are caught gracefully without crashing."""
    monkeypatch.setattr(posting_service.settings, "mock_mode", True)
    for p in posting_service.platforms:
        monkeypatch.setattr(p.settings, "mock_mode", True)

    twitter_platform = next(p for p in posting_service.platforms if p.platform_name == "X (Twitter)")

    mock_timeout = PlatformResult(
        platform="X (Twitter)",
        status="failed",
        is_mock=False,
        posted_url=None,
        public_access=False,
        date=None,
        time=None,
        error="Request timeout to X (Twitter) API gateway",
    )

    with patch.object(twitter_platform, "post", new_callable=AsyncMock, return_value=mock_timeout):
        payload = {"message": "Timeout test broadcast https://example.com/timeout"}
        response = client.post("/posting", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        tw_res = next(r for r in data["results"] if r["platform"] == "X (Twitter)")
        assert tw_res["status"] == "failed"
        assert "timeout" in tw_res["error"].lower()


def test_successful_response_without_post_id_does_not_fabricate_url():
    """
    Verify that platforms that do not return message permalinks (such as Slack incoming webhooks)
    set posted_url=None instead of fabricating random IDs.
    """
    slack_platform = next(p for p in posting_service.platforms if p.platform_name == "Slack")

    # Real Slack live webhook return: successful post without permalink
    real_slack_result = PlatformResult(
        platform="Slack",
        status="success",
        is_mock=False,
        posted_url=None,
        public_access=False,
        date="2026-11-18",
        time="11:30:00",
        error=None,
    )

    with patch.object(slack_platform, "post", new_callable=AsyncMock, return_value=real_slack_result):
        payload = {"message": "Slack live webhook verification https://example.com/announcement"}
        response = client.post("/posting", json=payload)
        assert response.status_code == 200

        data = response.json()
        slack_res = next(r for r in data["results"] if r["platform"] == "Slack")
        assert slack_res["status"] == "success"
        assert slack_res["posted_url"] is None
        assert slack_res["public_access"] is False


def test_all_platforms_failure_handling():
    """Verify graceful response when all platforms encounter errors."""
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
