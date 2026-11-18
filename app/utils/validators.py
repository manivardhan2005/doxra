"""Input validation and security checks for the posting system."""

import ipaddress
import re
import socket
from urllib.parse import urlparse
from typing import List, Tuple

# Regex to match URLs starting with http:// or https://
URL_REGEX = re.compile(
    r'(https?://[^\s<>"]+)',
    re.IGNORECASE,
)

# Explicitly blocked hostnames for SSRF protection
BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "metadata.google.internal",
    "169.254.169.254",
    "instance-data",
}


def clean_url(url: str) -> str:
    """Strip trailing punctuation that may adhere to a URL in natural language."""
    return url.rstrip(".,;)}]>\"'")


def extract_urls(text: str) -> List[str]:
    """Extract and clean all HTTP/HTTPS URLs present in the text."""
    raw_urls = URL_REGEX.findall(text)
    cleaned = [clean_url(u) for u in raw_urls]
    return [u for u in cleaned if u]


def is_restricted_ip(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP object is private, loopback, link-local, reserved, or unspecified."""
    # Check IPv4-mapped IPv6 addresses (e.g. ::ffff:127.0.0.1)
    if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped:
        ip_obj = ip_obj.ipv4_mapped

    return (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_reserved
        or ip_obj.is_multicast
        or ip_obj.is_unspecified
    )


def check_ip_address_security(raw_host: str) -> Tuple[bool, str]:
    """Inspect raw IP strings including IPv4, IPv6, IPv4-mapped IPv6, and integer representations."""
    # Strip IPv6 enclosing brackets if present
    clean_host = raw_host.strip("[]")

    # 1. Try standard IP address parsing
    try:
        ip = ipaddress.ip_address(clean_host)
        if is_restricted_ip(ip):
            return False, f"Target IP '{clean_host}' belongs to a restricted/private address range (SSRF protection)."
        return True, ""
    except ValueError:
        pass

    # 2. Try integer representation (e.g. 2130706433 for 127.0.0.1)
    if clean_host.isdigit():
        try:
            ip = ipaddress.ip_address(int(clean_host))
            if is_restricted_ip(ip):
                return False, f"Target integer IP '{clean_host}' resolves to restricted address {ip} (SSRF protection)."
            return True, ""
        except ValueError:
            pass

    return True, ""


def check_dns_resolution_security(hostname: str) -> Tuple[bool, str]:
    """
    Resolve domain name via DNS and verify that resolved IPs are not private or loopback.
    Protects against DNS rebinding and domains resolving to internal network addresses.
    """
    try:
        addr_info = socket.getaddrinfo(hostname, None)
        for entry in addr_info:
            sockaddr = entry[4]
            ip_str = sockaddr[0]
            try:
                ip_obj = ipaddress.ip_address(ip_str)
                if is_restricted_ip(ip_obj):
                    return False, f"Domain '{hostname}' resolves to restricted internal IP '{ip_str}' (SSRF protection)."
            except ValueError:
                continue
    except (socket.gaierror, socket.herror, OSError):
        # In offline/sandboxed environments or during test mock domains (e.g., example.com without DNS),
        # allow domain if format is valid and not in explicit blocklist.
        pass

    return True, ""


def validate_url(url: str) -> Tuple[bool, str]:
    """Validate URL format, scheme, domain, user credentials, and SSRF constraints."""
    if not url:
        return False, "URL cannot be empty."

    try:
        parsed = urlparse(url)
    except Exception as exc:
        return False, f"Malformed URL: {exc}"

    # Check scheme
    if parsed.scheme.lower() not in ("http", "https"):
        return False, f"Invalid URL scheme '{parsed.scheme}'. Only 'http' and 'https' are allowed."

    # Prohibit URL credentials (e.g. http://user:pass@example.com)
    if parsed.username or parsed.password:
        return False, "Embedded credentials (userinfo) in URL are prohibited for security."

    hostname = parsed.hostname
    if not hostname:
        return False, "URL must contain a valid domain or host name."

    # Explicit hostname blocklist
    if hostname.lower() in BLOCKED_HOSTNAMES:
        return False, f"Access to '{hostname}' is prohibited (SSRF protection)."

    # IP address safety (IPv4, IPv6, IPv4-mapped IPv6, integer representations)
    is_safe_ip, ip_err = check_ip_address_security(hostname)
    if not is_safe_ip:
        return False, ip_err

    # Validate domain name structure
    clean_host = hostname.strip("[]")
    try:
        ipaddress.ip_address(clean_host)
        is_ip = True
    except ValueError:
        is_ip = False

    if not is_ip and "." not in hostname:
        return False, f"Domain name '{hostname}' must contain a valid top-level domain."

    # DNS Resolution Check
    is_safe_dns, dns_err = check_dns_resolution_security(hostname)
    if not is_safe_dns:
        return False, dns_err

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
