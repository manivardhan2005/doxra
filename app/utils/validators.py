"""Input validation and security checks for the posting system."""

import ipaddress
import re
from urllib.parse import urlparse
from typing import List, Tuple

# Regex to match URLs starting with http:// or https://
URL_REGEX = re.compile(
    r'(https?://[^\s<>"]+)',
    re.IGNORECASE,
)

# Blocked hostnames for SSRF protection
BLOCKED_HOSTNAMES = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "metadata.google.internal",
    "169.254.169.254",
}


def clean_url(url: str) -> str:
    """Strip trailing punctuation that may adhere to a URL in natural language."""
    # Strip common trailing punctuation: '.', ',', ';', ')', ']', '}', '>'
    return url.rstrip(".,;)}]>\"'")


def extract_urls(text: str) -> List[str]:
    """Extract and clean all HTTP/HTTPS URLs present in the text."""
    raw_urls = URL_REGEX.findall(text)
    cleaned = [clean_url(u) for u in raw_urls]
    # Filter out empty or whitespace-only artifacts
    return [u for u in cleaned if u]


def is_private_or_loopback_ip(hostname: str) -> bool:
    """Check if the given hostname corresponds to a loopback, private, or link-local IP."""
    try:
        ip = ipaddress.ip_address(hostname)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        )
    except ValueError:
        # Not a raw IP address; standard domain name
        return False


def validate_url(url: str) -> Tuple[bool, str]:
    """Validate URL format, scheme, domain, and SSRF constraints."""
    if not url:
        return False, "URL cannot be empty."

    try:
        parsed = urlparse(url)
    except Exception as exc:
        return False, f"Malformed URL: {exc}"

    if parsed.scheme.lower() not in ("http", "https"):
        return False, f"Invalid URL scheme '{parsed.scheme}'. Only 'http' and 'https' are allowed."

    hostname = parsed.hostname
    if not hostname:
        return False, "URL must contain a valid domain or host name."

    # SSRF Protection: Check blocked hostnames
    if hostname.lower() in BLOCKED_HOSTNAMES:
        return False, f"Access to '{hostname}' is prohibited (SSRF protection)."

    # SSRF Protection: Check if IP is private/loopback
    if is_private_or_loopback_ip(hostname):
        return False, f"Target IP '{hostname}' belongs to a private/restricted address range (SSRF protection)."

    # Validate domain name format (e.g., example.com)
    if "." not in hostname and hostname.lower() != "localhost":
        return False, f"Domain name '{hostname}' must contain a valid top-level domain."

    return True, ""


def validate_posting_message(message: str) -> str:
    """
    Validate the input posting message according to assignment rules:
    1. Message must not exceed 200 characters.
    2. Exactly one CTA link must be included in the message.
    3. URL must be valid and pass security checks.

    Returns the single extracted and validated CTA URL.
    Raises ValueError with descriptive feedback on any violation.
    """
    if not message or not message.strip():
        raise ValueError("Message cannot be empty.")

    if len(message) > 200:
        raise ValueError(
            f"Message exceeds the 200 character limit (current length: {len(message)} characters)."
        )

    urls = extract_urls(message)

    if len(urls) == 0:
        raise ValueError("Message must include exactly one Call-to-Action (CTA) link. None was found.")

    if len(urls) > 1:
        raise ValueError(
            f"Message must include exactly one Call-to-Action (CTA) link. Found {len(urls)} links: {', '.join(urls)}."
        )

    cta_url = urls[0]
    is_valid, error_msg = validate_url(cta_url)
    if not is_valid:
        raise ValueError(f"Invalid CTA link '{cta_url}': {error_msg}")

    return cta_url
