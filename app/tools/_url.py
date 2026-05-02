import ipaddress
from urllib.parse import urlparse


def _validate_url(url: str) -> str:
    """Normalize and validate a URL, rejecting non-web schemes and internal hosts.

    Returns the original URL unchanged on success.
    Raises ValueError with a descriptive message on validation failure.
    """
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"URL scheme must be http or https, got: {parsed.scheme}")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL must contain a valid hostname")

    # Block well-known internal / loopback hostnames
    if hostname.lower() in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
        raise ValueError(f"Access to internal host blocked: {hostname}")

    # Block private / loopback / reserved IP ranges
    try:
        addr = ipaddress.ip_address(hostname)
        if addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_unspecified:
            raise ValueError(f"Access to internal IP blocked: {hostname}")
    except ValueError:
        # Not an IP address (e.g. example.com) — acceptable
        pass

    return url
