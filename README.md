# Automated Multi-Platform Posting System API

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.10%20|%203.11%20|%203.12%20|%203.13-blue.svg)](https://www.python.org/)
[![Pydantic](https://img.shields.io/badge/Pydantic-v2.5+-E92063.svg)](https://docs.pydantic.dev/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-12%20Passing-brightgreen.svg)]()

A high-performance, asynchronous REST API service built with **Python 3.x** and **FastAPI** that automatically publishes short promotional and marketing messages across multiple third-party social media platforms, communication channels, and web portals concurrently with complete fault isolation and enterprise-grade input validation.

---

## Table of Contents

1. [Objective & Architecture](#objective--architecture)
2. [Supported Platforms & API Research](#supported-platforms--api-research)
3. [Input Validation & Security Rules](#input-validation--security-rules)
4. [Project Structure](#project-structure)
5. [Installation & Setup](#installation--setup)
6. [API Specification](#api-specification)
   - [Endpoint Details](#endpoint-details)
   - [Sample Request](#sample-request)
   - [Sample Success Response](#sample-success-response)
   - [Sample Validation Error Response](#sample-validation-error-response)
7. [Testing & Verification](#testing--verification)
8. [Configuration & Environment Variables](#configuration--environment-variables)
9. [Submission & Verification Checklist](#submission--verification-checklist)

---

## Objective & Architecture

Modern digital distribution requires organizations to broadcast updates, announcements, and promotional campaigns across diverse channels simultaneously. This system provides a unified `POST /posting` API that:

1. **Validates Input Strictness**: Enforces length constraints ($\le 200$ characters), requires exactly one Call-to-Action (CTA) link, and guards against Server-Side Request Forgery (SSRF).
2. **Internal Platform Selection**: Intelligently routes messages across 6 independent platform adapters without requiring caller platform orchestration.
3. **Concurrent Async Execution**: Leverages Python's `asyncio` and `httpx` asynchronous HTTP clients to dispatch requests concurrently via `asyncio.gather(..., return_exceptions=True)`.
4. **Fault Isolation**: Ensures failures on one platform (e.g. invalid tokens, rate limits, network timeouts) never compromise or delay broadcasts to remaining platforms.
5. **Standardized Audit Results**: Returns structured JSON detailing individual platform statuses, direct published URLs, public visibility status, and UTC timestamps.

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
|  - URL syntax & domain format validation                                |
|  - SSRF protection (Blocks localhost, private subnets, cloud metadata)  |
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
| 1 | **Telegram** | `POST https://api.telegram.org/bot<token>/sendMessage` | Bot Token (`BotFather`) | **Yes** (Public Channel) | [Telegram Bot API Docs](https://core.telegram.org/bots/api#sendmessage) |
| 2 | **Discord** | `POST https://discord.com/api/webhooks/<id>/<token>?wait=true` | Webhook URL Token | **Yes** (Public Server) | [Discord Webhooks Reference](https://discord.com/developers/docs/resources/webhook) |
| 3 | **Slack** | `POST https://hooks.slack.com/services/...` | Incoming Webhook Secret | **No** (Workspace Private) | [Slack Incoming Webhooks](https://api.slack.com/messaging/webhooks) |
| 4 | **X (Twitter)** | `POST https://api.twitter.com/2/tweets` | OAuth 2.0 / Bearer Token | **Yes** (Public Tweet) | [X API v2 Post Tweets](https://developer.x.com/en/docs/twitter-api/tweets/manage-tweets/api-reference/post-tweets) |
| 5 | **Mastodon** | `POST {instance}/api/v1/statuses` | Bearer Access Token | **Yes** (Federated Public) | [Mastodon Statuses API](https://docs.joinmastodon.org/methods/statuses/#create) |
| 6 | **LinkedIn** | `POST https://api.linkedin.com/v2/ugcPosts` | OAuth 2.0 Bearer Token | **Yes** (Public Post) | [LinkedIn Consumer Share API](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/share-on-linkedin) |

---

## Input Validation & Security Rules

To ensure reliable operation and adhere to the practical test criteria, the application implements strict domain validators:

1. **Character Constraint**: The entire message payload must not exceed **200 characters** (`len(message) <= 200`).
2. **Single CTA Link**:
   - Exactly **one** valid HTTP/HTTPS URL must be included in the message.
   - Messages with 0 links return a `422 Unprocessable Entity` error.
   - Messages with 2 or more links return a `422 Unprocessable Entity` error.
3. **URL Scheme & Structure**: The CTA link must strictly use `http` or `https` and possess a valid domain name.
4. **SSRF (Server-Side Request Forgery) Protection**:
   - Prohibits target links pointing to `localhost`, `127.0.0.1`, `0.0.0.0`, or `::1`.
   - Prohibits private RFC 1918 subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`).
   - Prohibits cloud instance metadata addresses (`169.254.169.254`, `metadata.google.internal`).

---

## Project Structure

```text
automated-posting/
│
├── app/
│   ├── __init__.py               # Application package marker
│   ├── main.py                   # FastAPI initialization, routing & exception handlers
│   ├── schemas.py                # Pydantic models for request, response, and platform results
│   ├── config.py                 # Environment settings & configuration singleton
│   │
│   ├── platforms/                # Modular platform adapters
│   │   ├── __init__.py           # Platform registry & exports
│   │   ├── base.py               # Abstract BasePlatform with shared contracts
│   │   ├── telegram.py           # Telegram Bot API implementation
│   │   ├── discord.py            # Discord Webhook API implementation
│   │   ├── slack.py              # Slack Incoming Webhook implementation
│   │   ├── twitter.py            # X (Twitter) API v2 implementation
│   │   ├── mastodon.py           # Mastodon REST API implementation
│   │   └── linkedin.py           # LinkedIn UGC Posts API implementation
│   │
│   ├── services/
│   │   ├── __init__.py           # Service package exports
│   │   └── posting_service.py    # Multi-platform async broadcast orchestrator
│   │
│   └── utils/
│       ├── __init__.py           # Utility exports
│       └── validators.py         # URL extraction, CTA validation & SSRF security
│
├── tests/
│   ├── __init__.py               # Test package marker
│   └── test_posting.py           # 12 comprehensive unit & integration tests
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
git clone https://github.com/YOUR_USERNAME/automated-multi-platform-poster.git
cd automated-multi-platform-poster
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

> **Note on Mock Mode**:  
> By default, `MOCK_MODE=true` is enabled in `.env`. This allows the technical review team to test and execute the application immediately out of the box without requiring private API tokens for all 6 platforms.  
> When ready for production, configure your live platform credentials and set `MOCK_MODE=false`.

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

### Sample Success Response (`HTTP 200 OK`)

```json
{
  "success": true,
  "total_platforms": 6,
  "successful_posts": 6,
  "failed_posts": 0,
  "results": [
    {
      "platform": "Telegram",
      "status": "success",
      "posted_url": "https://t.me/dxoratech/23845",
      "public_access": true,
      "date": "2026-11-18",
      "time": "06:12:04",
      "error": null
    },
    {
      "platform": "Discord",
      "status": "success",
      "posted_url": "https://discord.com/channels/998877665544332211/112233445566778899/407822684746058361",
      "public_access": true,
      "date": "2026-11-18",
      "time": "06:12:04",
      "error": null
    },
    {
      "platform": "Slack",
      "status": "success",
      "posted_url": "https://app.slack.com/client/T01234567/C09876543/thread/1794982324.954000",
      "public_access": false,
      "date": "2026-11-18",
      "time": "06:12:04",
      "error": null
    },
    {
      "platform": "X (Twitter)",
      "status": "success",
      "posted_url": "https://x.com/dxoratech/status/1810831393448961388",
      "public_access": true,
      "date": "2026-11-18",
      "time": "06:12:04",
      "error": null
    },
    {
      "platform": "Mastodon",
      "status": "success",
      "posted_url": "https://mastodon.social/@dxora/112197850334108768",
      "public_access": true,
      "date": "2026-11-18",
      "time": "06:12:04",
      "error": null
    },
    {
      "platform": "LinkedIn",
      "status": "success",
      "posted_url": "https://www.linkedin.com/feed/update/urn:li:share:7151541026161385658",
      "public_access": true,
      "date": "2026-11-18",
      "time": "06:12:04",
      "error": null
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

## Testing & Verification

The project includes an automated test suite with **12 comprehensive tests** covering input validation, URL security, fault isolation, and API responses.

### Running Tests
Execute `pytest` from the root directory:
```bash
pytest tests/ -v
```

### Test Suite Output
```text
============================= test session starts =============================
platform win32 -- Python 3.13.4, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\...\automated-posting
collected 12 items

tests/test_posting.py::test_root_endpoint PASSED                         [  8%]
tests/test_posting.py::test_health_check_endpoint PASSED                 [ 16%]
tests/test_posting.py::test_openapi_schema_endpoint PASSED               [ 25%]
tests/test_posting.py::test_successful_multi_platform_posting PASSED     [ 33%]
tests/test_posting.py::test_validation_error_message_too_long PASSED     [ 41%]
tests/test_posting.py::test_validation_error_missing_cta_link PASSED     [ 50%]
tests/test_posting.py::test_validation_error_multiple_cta_links PASSED   [ 58%]
tests/test_posting.py::test_validation_error_invalid_url_scheme PASSED   [ 66%]
tests/test_posting.py::test_validation_error_ssrf_localhost PASSED       [ 75%]
tests/test_posting.py::test_validation_error_ssrf_private_ip PASSED      [ 83%]
tests/test_posting.py::test_platform_failure_isolation PASSED            [ 91%]
tests/test_posting.py::test_all_platforms_failure_handling PASSED        [100%]

======================= 12 passed in 0.77s ========================
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
| `TWITTER_BEARER_TOKEN` | string | `None` | Twitter API v2 Bearer Token |
| `MASTODON_INSTANCE_URL` | string | `https://mastodon.social` | Mastodon instance domain |
| `MASTODON_ACCESS_TOKEN` | string | `None` | Mastodon OAuth access token |
| `LINKEDIN_ACCESS_TOKEN` | string | `None` | LinkedIn Developer OAuth Bearer Token |

---

## Submission & Verification Checklist

- [x] Python 3.x with FastAPI and Uvicorn
- [x] Input validation ($\le 200$ characters, exactly 1 CTA link)
- [x] SSRF protection against private IP and loopback addresses
- [x] 6 independent platform integrations (Telegram, Discord, Slack, X, Mastodon, LinkedIn)
- [x] Concurrency with fault isolation (single platform failure does not block others)
- [x] Returns structured results matching the specification schema
- [x] Server runs at `http://localhost:4000` with interactive docs at `/docs`
- [x] 12 unit and integration tests passing (`pytest tests/ -v`)
- [x] Clean repository without API keys, passwords, or private credentials
- [x] Public GitHub repository ready for submission

### Email Submission Details
- **To**: [hr@chivoxai.com](mailto:hr@chivoxai.com)
- **Subject**: `[Your Name] - Python Practical test review`
- **Required Info**: Full Name, Public GitHub Repository Link, Contact Number, Current Location, Preferred Date and Time for Final Discussion.
- **Verification Links**:
  - Dxora Technologies LinkedIn: [https://www.linkedin.com/company/dxora-technologies](https://www.linkedin.com/company/dxora-technologies)
  - CREST Instagram: [https://www.instagram.com/crestspot/](https://www.instagram.com/crestspot/)
