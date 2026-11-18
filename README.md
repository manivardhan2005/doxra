# Automated Multi-Platform Posting System API

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.10%20|%203.11%20|%203.12%20|%203.13-blue.svg)](https://www.python.org/)
[![Pydantic](https://img.shields.io/badge/Pydantic-v2.5+-E92063.svg)](https://docs.pydantic.dev/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-19%20Passing-brightgreen.svg)]()

A high-performance, asynchronous REST API service built with **Python 3.x** and **FastAPI** that automatically publishes short promotional and marketing messages across multiple third-party social media platforms, communication channels, and web portals concurrently with complete fault isolation, enterprise-grade input validation, and SSRF defense.

---

## Table of Contents

1. [Objective & Architecture](#objective--architecture)
2. [Supported Platforms & API Research](#supported-platforms--api-research)
3. [Authentication & Realistic Permalink Handling](#authentication--realistic-permalink-handling)
4. [Input Validation & Advanced SSRF Hardening](#input-validation--advanced-ssrf-hardening)
5. [Mock Mode vs Production Mode](#mock-mode-vs-production-mode)
6. [Project Structure](#project-structure)
7. [Installation & Setup](#installation--setup)
8. [API Specification](#api-specification)
   - [Endpoint Details](#endpoint-details)
   - [Sample Request](#sample-request)
   - [Sample Simulated Response (Mock Mode)](#sample-simulated-response-mock-mode)
   - [Sample Live Production Response](#sample-live-production-response)
   - [Sample Validation Error Response](#sample-validation-error-response)
9. [Automated Test Suite (19 Tests)](#automated-test-suite-19-tests)
10. [Configuration & Environment Variables](#configuration--environment-variables)
11. [Submission & Verification Checklist](#submission--verification-checklist)

---

## Objective & Architecture

Modern digital distribution requires organizations to broadcast updates, announcements, and promotional campaigns across diverse channels simultaneously. This system provides a unified `POST /posting` API that:

1. **Validates Input Strictness**: Enforces length constraints ($\le 200$ characters), requires exactly one Call-to-Action (CTA) link, and guards against Server-Side Request Forgery (SSRF).
2. **Internal Platform Selection**: Intelligently routes messages across 6 independent platform adapters without requiring caller platform orchestration.
3. **Concurrent Async Execution**: Leverages Python's `asyncio` and `httpx` asynchronous HTTP clients to dispatch requests concurrently via `asyncio.gather(..., return_exceptions=True)`.
4. **Fault Isolation**: Ensures failures on one platform (e.g. invalid tokens, rate limits, network timeouts) never compromise or delay broadcasts to remaining platforms.
5. **Accurate Audit Results**: Returns structured JSON with explicit status distinctions (`simulated` vs `success` vs `failed`), real published URLs where supported by API responses, and UTC timestamps.

### High-Level Architecture Flow

```
+-------------------------------------------------------------------------+
|                              FastAPI Client                             |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                          Input Validation Layer                         |
|  - Max 200 characters limit check                                       |
|  - Exactly 1 CTA link check (Regex & RFC parser)                        |
|  - Embedded credential (userinfo) check                                 |
|  - SSRF protection (IPv4, IPv6, IPv4-mapped, integer IPs, DNS check)    |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                             PostingService                              |
|           Async Concurrent Broadcast (`asyncio.gather`)                 |
+-------------------------------------------------------------------------+
       |               |              |             |            |            |
       v               v              v             v            v            v
+-------------+ +-------------+ +-----------+ +-----------+ +----------+ +----------+
|  Telegram   | |   Discord   | |   Slack   | |X (Twitter)| | Mastodon | | LinkedIn |
|   Bot API   | |   Webhook   | |  Webhook  | |  API v2   | | REST API | | UGC API  |
+-------------+ +-------------+ +-----------+ +-----------+ +----------+ +----------+
```

---

## Supported Platforms & API Research

The system integrates with **6 major third-party platforms** (exceeding the assignment requirement of at least 5):

| # | Platform | Official API Integration | Auth Method | Public Access | Official Documentation Reference |
|---|---|---|---|---|---|
| 1 | **Telegram** | `POST https://api.telegram.org/bot<token>/sendMessage` | Bot Token (`BotFather`) | **Yes** (Public Channel) / **No** (Private Group) | [Telegram Bot API Docs](https://core.telegram.org/bots/api#sendmessage) |
| 2 | **Discord** | `POST https://discord.com/api/webhooks/<id>/<token>?wait=true` | Webhook URL Token | **Yes** (Public Server) | [Discord Webhooks Reference](https://discord.com/developers/docs/resources/webhook) |
| 3 | **Slack** | `POST https://hooks.slack.com/services/...` | Incoming Webhook Secret | **No** (Workspace Internal) | [Slack Incoming Webhooks](https://api.slack.com/messaging/webhooks) |
| 4 | **X (Twitter)** | `POST https://api.twitter.com/2/tweets` | OAuth 1.0a User Context / OAuth 2.0 User Token | **Yes** (Public Tweet) | [X API v2 Post Tweets](https://developer.x.com/en/docs/twitter-api/tweets/manage-tweets/api-reference/post-tweets) |
| 5 | **Mastodon** | `POST {instance}/api/v1/statuses` | Bearer Access Token | **Yes** (Federated Public) | [Mastodon Statuses API](https://docs.joinmastodon.org/methods/statuses/#create) |
| 6 | **LinkedIn** | `POST https://api.linkedin.com/v2/ugcPosts` | OAuth 2.0 Bearer Token | **Yes** (Public Post) | [LinkedIn Consumer Share API](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/share-on-linkedin) |

---

## Authentication & Realistic Permalink Handling

### 1. X (Twitter) User-Context Authentication
X API v2 `/2/tweets` requires **User-Context** authorization (an app-only Bearer token is rejected by X for tweet creation). The adapter implements:
- **OAuth 1.0a User Context (RFC 5849)**: Generates HMAC-SHA1 signatures using Consumer Key, Consumer Secret, Access Token, and Access Token Secret.
- **OAuth 2.0 User Token**: Supports user tokens created with the `tweet.write` scope.

### 2. Honest Permalink Generation (No Fabricated IDs)
- **Slack**: Incoming Webhooks return `"ok"` to indicate successful broadcast, but do not provide public permalinks. The adapter honestly sets `posted_url: null` and `public_access: false` instead of fabricating fake timestamp URLs.
- **Discord**: Uses `?wait=true` to capture Discord's message object (`id`, `channel_id`). Only sets `posted_url` if the IDs are returned in Discord's actual response.
- **Telegram**: Distinguishes public channel usernames (`@channel` $\rightarrow$ `https://t.me/channel/{id}`) from private numeric chat IDs (`-100...` $\rightarrow$ `public_access: false`).
- **LinkedIn**: Extracts the actual share URN (`urn:li:share:{id}`) returned by the UGC API without fabricating random IDs.

---

## Input Validation & Advanced SSRF Hardening

1. **Character Constraint**: The entire message payload must not exceed **200 characters** (`len(message) <= 200`).
2. **Single CTA Link**: Exactly **one** valid HTTP/HTTPS URL must be included in the message. Zero or multiple links are rejected with HTTP 422.
3. **URL Credentials**: Embedded credentials (`http://user:pass@host`) are strictly prohibited to prevent credential leakage.
4. **Comprehensive SSRF Defense**:
   - Blocks loopback addresses: `localhost`, `127.0.0.1`, `::1`.
   - Blocks IPv6 loopback (`::1`), link-local (`fe80::/10`), and IPv4-mapped IPv6 (`::ffff:127.0.0.1`).
   - Blocks alternative integer IP representations (e.g. `2130706433` resolving to `127.0.0.1`).
   - Blocks private RFC 1918 subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`).
   - Blocks cloud instance metadata endpoints (`169.254.169.254`, `metadata.google.internal`).
   - **DNS Resolution Check**: Resolves hostnames via `socket.getaddrinfo` to catch DNS rebinding and domains resolving to internal IP addresses.

---

## Mock Mode vs Production Mode

To support evaluation without requiring live API keys for all 6 platforms, the system provides an explicit mode distinction:

- **Mock Mode (`MOCK_MODE=true`)**:
  - Automatically simulates posting for quick evaluation.
  - Returns `status: "simulated"` and `is_mock: true`.
  - Preview URLs are explicitly identified as simulated previews.
- **Production Mode (`MOCK_MODE=false`)**:
  - Unconfigured platforms return `status: "failed"` with `"Platform credentials are not configured"`.
  - Configured platforms make live, authenticated HTTP REST API calls.

---

## Project Structure

```text
doxra/
│
├── app/
│   ├── __init__.py               # Application package marker
│   ├── main.py                   # FastAPI initialization, routing & exception handlers
│   ├── schemas.py                # Pydantic models with explicit mock status flags
│   ├── config.py                 # Environment settings & configuration singleton
│   │
│   ├── platforms/                # Modular platform adapters
│   │   ├── __init__.py           # Platform registry & exports
│   │   ├── base.py               # Abstract BasePlatform with success, mock & failure helpers
│   │   ├── telegram.py           # Telegram Bot API implementation
│   │   ├── discord.py            # Discord Webhook API implementation
│   │   ├── slack.py              # Slack Incoming Webhook implementation
│   │   ├── twitter.py            # X (Twitter) API v2 with OAuth 1.0a / OAuth 2.0 user context
│   │   ├── mastodon.py           # Mastodon REST API implementation
│   │   └── linkedin.py           # LinkedIn UGC Posts API implementation
│   │
│   ├── services/
│   │   ├── __init__.py           # Service package exports
│   │   └── posting_service.py    # Multi-platform async broadcast orchestrator
│   │
│   └── utils/
│       ├── __init__.py           # Utility exports
│       └── validators.py         # CTA extraction, URL validator & hardened SSRF defense
│
├── tests/
│   ├── __init__.py               # Test package marker
│   └── test_posting.py           # 19 comprehensive unit & integration tests
│
├── .env.example                  # Environment configuration template
├── .env                          # Local environment variables
├── .gitignore                    # Git exclusions
├── requirements.txt              # Production and test dependencies
└── README.md                     # Complete project documentation
```

---

## Installation & Setup

### 1. Prerequisites
- **Python 3.10+** (Tested on Python 3.13)
- `pip` package manager

### 2. Clone the Repository
```bash
git clone https://github.com/manivardhan2005/doxra.git
cd doxra
```

### 3. Create and Activate a Virtual Environment
```bash
# On Linux / macOS
python3 -m venv venv
source venv/bin/activate

# On Windows
python -m venv venv
.\venv\Scripts\activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

### 6. Start the FastAPI Local Server
Run the application using Uvicorn on port **4000**:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 4000
```

### 7. Interactive API Documentation
Open your web browser and navigate to:
- **Swagger UI**: [http://localhost:4000/docs](http://localhost:4000/docs)
- **ReDoc**: [http://localhost:4000/redoc](http://localhost:4000/redoc)
- **Health Endpoint**: [http://localhost:4000/health](http://localhost:4000/health)

---

## API Specification

### Endpoint Details

- **Method**: `POST`
- **URL**: `http://localhost:4000/posting`
- **Content-Type**: `application/json`

---

### Sample Request

```bash
curl -X POST "http://localhost:4000/posting" \
     -H "Content-Type: application/json" \
     -d '{
       "message": "Check out our latest business platform and grow your online visibility. https://example.com"
     }'
```

---

### Sample Simulated Response (Mock Mode)

```json
{
  "success": true,
  "mock_mode": true,
  "total_platforms": 6,
  "successful_posts": 6,
  "failed_posts": 0,
  "results": [
    {
      "platform": "Telegram",
      "status": "simulated",
      "is_mock": true,
      "posted_url": "https://t.me/dxoratech_preview/simulated-post",
      "public_access": true,
      "date": "2026-11-18",
      "time": "06:30:00",
      "error": null
    },
    {
      "platform": "Discord",
      "status": "simulated",
      "is_mock": true,
      "posted_url": "https://discord.com/channels/mock_guild/mock_channel/simulated_post",
      "public_access": true,
      "date": "2026-11-18",
      "time": "06:30:00",
      "error": null
    },
    {
      "platform": "Slack",
      "status": "simulated",
      "is_mock": true,
      "posted_url": "https://app.slack.com/client/mock_workspace/mock_channel",
      "public_access": false,
      "date": "2026-11-18",
      "time": "06:30:00",
      "error": null
    },
    {
      "platform": "X (Twitter)",
      "status": "simulated",
      "is_mock": true,
      "posted_url": "https://x.com/dxoratech/status/simulated_tweet",
      "public_access": true,
      "date": "2026-11-18",
      "time": "06:30:00",
      "error": null
    },
    {
      "platform": "Mastodon",
      "status": "simulated",
      "is_mock": true,
      "posted_url": "https://mastodon.social/@dxora/simulated_status",
      "public_access": true,
      "date": "2026-11-18",
      "time": "06:30:00",
      "error": null
    },
    {
      "platform": "LinkedIn",
      "status": "simulated",
      "is_mock": true,
      "posted_url": "https://www.linkedin.com/feed/update/urn:li:share:simulated_share",
      "public_access": true,
      "date": "2026-11-18",
      "time": "06:30:00",
      "error": null
    }
  ]
}
```

---

### Sample Live Production Response (Unconfigured Platform Isolation)

When `MOCK_MODE=false` and credentials are not provided:

```json
{
  "success": false,
  "mock_mode": false,
  "total_platforms": 6,
  "successful_posts": 0,
  "failed_posts": 6,
  "results": [
    {
      "platform": "Telegram",
      "status": "failed",
      "is_mock": false,
      "posted_url": null,
      "public_access": false,
      "date": null,
      "time": null,
      "error": "Telegram credentials not configured (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID required)"
    },
    {
      "platform": "Slack",
      "status": "failed",
      "is_mock": false,
      "posted_url": null,
      "public_access": false,
      "date": null,
      "time": null,
      "error": "Slack webhook URL is not configured (SLACK_WEBHOOK_URL required)"
    }
  ]
}
```

---

### Sample Validation Error Response (`HTTP 422 Unprocessable Entity`)

#### Case 1: Missing CTA Link
```json
{
  "success": false,
  "error": "Validation Error",
  "detail": "Message must include exactly one Call-to-Action (CTA) link. None was found.",
  "results": []
}
```

#### Case 2: Exceeding 200 Characters Limit
```json
{
  "success": false,
  "error": "Validation Error",
  "detail": "String should have at most 200 characters",
  "results": []
}
```

#### Case 3: SSRF Prohibited URL
```json
{
  "success": false,
  "error": "Validation Error",
  "detail": "Invalid CTA link 'http://localhost:8080/admin': Access to 'localhost' is prohibited (SSRF protection).",
  "results": []
}
```

---

## Automated Test Suite (19 Tests)

The test suite contains **19 comprehensive tests** covering input validation, URL security, mock/production mode boundaries, rate limiting, and fault isolation:

### Running Tests
Execute `pytest` from the root directory:
```bash
pytest tests/ -v
```

### Test Suite Execution Summary
```text
============================= test session starts =============================
platform win32 -- Python 3.13.4, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\...\doxra
collected 19 items

tests/test_posting.py::test_root_endpoint PASSED                         [  5%]
tests/test_posting.py::test_health_check_endpoint PASSED                 [ 10%]
tests/test_posting.py::test_openapi_schema_endpoint PASSED               [ 15%]
tests/test_posting.py::test_mock_mode_explicitly_identifies_simulated_results PASSED [ 21%]
tests/test_posting.py::test_mock_mode_disabled_missing_credentials_fails PASSED [ 26%]
tests/test_posting.py::test_validation_error_message_too_long PASSED     [ 31%]
tests/test_posting.py::test_validation_error_missing_cta_link PASSED     [ 36%]
tests/test_posting.py::test_validation_error_multiple_cta_links PASSED   [ 42%]
tests/test_posting.py::test_validation_error_invalid_url_scheme PASSED   [ 47%]
tests/test_posting.py::test_validation_error_url_credentials_prohibited PASSED [ 52%]
tests/test_posting.py::test_validation_error_ssrf_localhost PASSED       [ 57%]
tests/test_posting.py::test_validation_error_ssrf_private_ip PASSED      [ 63%]
tests/test_posting.py::test_validation_error_ssrf_ipv6_loopback_and_linklocal PASSED [ 68%]
tests/test_posting.py::test_validation_error_dns_resolves_to_private_ip PASSED [ 73%]
tests/test_posting.py::test_platform_failure_isolation PASSED            [ 78%]
tests/test_posting.py::test_platform_rate_limit_429_captured PASSED      [ 84%]
tests/test_posting.py::test_platform_timeout_captured PASSED             [ 89%]
tests/test_posting.py::test_successful_response_without_post_id_does_not_fabricate_url PASSED [ 94%]
tests/test_posting.py::test_all_platforms_failure_handling PASSED        [100%]

======================= 19 passed in 0.46s ========================
```

---

## Configuration & Environment Variables

| Variable | Type | Default | Description |
|---|---|---|---|
| `MOCK_MODE` | boolean | `true` | When true, simulates platform APIs for evaluation without live credentials |
| `HOST` | string | `0.0.0.0` | Server host binding |
| `PORT` | integer | `4000` | Port for the FastAPI server |
| `REQUEST_TIMEOUT_SECONDS` | float | `10.0` | Maximum timeout for external platform HTTP requests |
| `TELEGRAM_BOT_TOKEN` | string | `None` | Telegram bot authentication token |
| `TELEGRAM_CHAT_ID` | string | `None` | Channel or group chat ID |
| `DISCORD_WEBHOOK_URL` | string | `None` | Discord webhook URL |
| `SLACK_WEBHOOK_URL` | string | `None` | Slack incoming webhook URL |
| `TWITTER_API_KEY` | string | `None` | X (Twitter) Consumer API Key |
| `TWITTER_API_SECRET` | string | `None` | X (Twitter) Consumer API Secret |
| `TWITTER_ACCESS_TOKEN` | string | `None` | X (Twitter) OAuth 1.0a / OAuth 2.0 User Access Token |
| `TWITTER_ACCESS_TOKEN_SECRET` | string | `None` | X (Twitter) OAuth 1.0a Access Token Secret |
| `MASTODON_INSTANCE_URL` | string | `https://mastodon.social` | Mastodon instance domain |
| `MASTODON_ACCESS_TOKEN` | string | `None` | Mastodon OAuth access token |
| `LINKEDIN_ACCESS_TOKEN` | string | `None` | LinkedIn Developer OAuth Bearer Token |
| `LINKEDIN_AUTHOR_URN` | string | `urn:li:organization:...` | LinkedIn Author URN |

---

## Submission & Verification Checklist

- [x] Python 3.x with FastAPI and Uvicorn
- [x] Input validation ($\le 200$ characters, exactly 1 CTA link)
- [x] Hardened SSRF defense (IPv4/IPv6, integer IPs, user credentials, DNS check)
- [x] 6 independent platform integrations (Telegram, Discord, Slack, X, Mastodon, LinkedIn)
- [x] X (Twitter) user-context authentication (OAuth 1.0a & OAuth 2.0)
- [x] Honest permalink generation without fabricating fake message IDs
- [x] Explicit mock mode (`is_mock: true`, `status: "simulated"`) vs production mode
- [x] Concurrency with fault isolation (single platform failure does not block others)
- [x] Server runs at `http://localhost:4000` with interactive docs at `/docs`
- [x] 19 unit and integration tests passing (`pytest tests/ -v`)
- [x] Clean repository without API keys, passwords, or private credentials
- [x] Public GitHub repository ready for submission: [https://github.com/manivardhan2005/doxra](https://github.com/manivardhan2005/doxra)

### Email Submission Details
- **To**: [hr@chivoxai.com](mailto:hr@chivoxai.com)
- **Subject**: `Mani Vardhan - Python Practical test review`
- **Required Info**: Full Name, Public GitHub Repository Link, Contact Number, Current Location, Preferred Date and Time for Final Discussion.
- **Verification Links**:
  - Dxora Technologies LinkedIn: [https://www.linkedin.com/company/dxora-technologies](https://www.linkedin.com/company/dxora-technologies)
  - CREST Instagram: [https://www.instagram.com/crestspot/](https://www.instagram.com/crestspot/)
