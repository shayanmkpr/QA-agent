"""Tests for app.tools._url"""

import pytest
from app.tools._url import _validate_url


# Happy path tests


def test_validate_url_https():
    """A regular HTTPS URL should pass validation unchanged."""
    url = "https://example.com"
    assert _validate_url(url) == url


def test_validate_url_http():
    """A regular HTTP URL should pass validation unchanged."""
    url = "http://example.com"
    assert _validate_url(url) == url


# Rejected schemes


def test_validate_url_rejects_ftp():
    """FTP scheme is not allowed."""
    with pytest.raises(ValueError, match="URL scheme must be http or https"):
        _validate_url("ftp://example.com")


def test_validate_url_rejects_file():
    """File scheme is not allowed."""
    with pytest.raises(ValueError, match="URL scheme must be http or https"):
        _validate_url("file:///etc/passwd")


def test_validate_url_rejects_empty_scheme():
    """Missing scheme is not allowed."""
    with pytest.raises(ValueError, match="URL scheme must be http or https"):
        _validate_url("example.com")


# Blocked hosts


def test_validate_url_rejects_localhost():
    """localhost is an internal host and should be blocked."""
    with pytest.raises(ValueError, match="Access to internal host blocked"):
        _validate_url("http://localhost:8080")


def test_validate_url_rejects_127_0_0_1():
    """127.0.0.1 is a loopback address and should be blocked."""
    with pytest.raises(ValueError, match="Access to internal host blocked"):
        _validate_url("https://127.0.0.1")


def test_validate_url_rejects_0_0_0_0():
    """0.0.0.0 is blocked."""
    with pytest.raises(ValueError, match="Access to internal host blocked"):
        _validate_url("http://0.0.0.0")


def test_validate_url_rejects_private_ipv4():
    """Private IP range like 192.168.x.x is blocked."""
    with pytest.raises(ValueError, match="Access to internal IP blocked"):
        _validate_url("https://192.168.1.1")


def test_validate_url_rejects_private_ipv6():
    """Private IPv6 address like ::1 is blocked."""
    with pytest.raises(ValueError, match="Access to internal host blocked"):
        _validate_url("https://[::1]")


# Hostname variations


def test_validate_url_allows_subdomain():
    """Subdomains of public domains are allowed."""
    url = "https://api.github.com"
    assert _validate_url(url) == url


def test_validate_url_preserves_query_params():
    """Query parameters should be preserved after validation."""
    url = "https://example.com?foo=bar&baz=qux"
    assert _validate_url(url) == url


def test_validate_url_preserves_path():
    """Paths should be preserved after validation."""
    url = "https://example.com/foo/bar"
    assert _validate_url(url) == url
