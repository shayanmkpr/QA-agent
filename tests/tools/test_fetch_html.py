"""Tests for app.tools.fetch_html"""

from unittest.mock import MagicMock, patch

from app.tools.fetch_html import fetch_html


def test_fetch_html_valid_url():
    """fetch_html should call the browser manager and return HTML."""
    fake_html = "<html><body>Hello!</body></html>"
    fake_browser = MagicMock()
    fake_browser.get_html.return_value = fake_html

    with patch("app.tools.fetch_html.get_browser_manager", return_value=fake_browser):
        result = fetch_html.invoke({"url": "https://example.com"})

    fake_browser.get_html.assert_called_once_with("https://example.com")
    assert result == fake_html


def test_fetch_html_invalid_url():
    """A bad URL should raise a ValueError before reaching the browser."""
    with patch("app.tools.fetch_html.get_browser_manager") as mock_bm:
        import pytest

        with pytest.raises(ValueError, match="URL scheme must be http or https"):
            fetch_html.invoke({"url": "ftp://bad-scheme.com"})
        mock_bm.assert_not_called()


def test_fetch_html_rejects_localhost():
    """fetch_html should block localhost and never call the browser."""
    with patch("app.tools.fetch_html.get_browser_manager") as mock_bm:
        import pytest

        with pytest.raises(ValueError, match="internal"):
            fetch_html.invoke({"url": "http://localhost"})
        mock_bm.assert_not_called()
