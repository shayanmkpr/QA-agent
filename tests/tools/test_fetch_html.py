"""Tests for app.tools.fetch_html"""

from unittest.mock import MagicMock, patch

from app.tools.fetch_html import fetch_html


def test_fetch_html_with_url():
    fake_html = "<html><body>Hello!</body></html>"
    fake_browser = MagicMock()
    fake_browser.get_current_html.return_value = fake_html

    with patch("app.tools.fetch_html.get_browser_manager", return_value=fake_browser):
        result = fetch_html.invoke({"url": "https://example.com"})

    fake_browser.navigate.assert_called_once_with("https://example.com")
    fake_browser.get_current_html.assert_called_once()
    assert result == fake_html


def test_fetch_html_no_url():
    fake_html = "<html><body>Current page</body></html>"
    fake_browser = MagicMock()
    fake_browser.get_current_html.return_value = fake_html

    with patch("app.tools.fetch_html.get_browser_manager", return_value=fake_browser):
        result = fetch_html.invoke({})

    fake_browser.navigate.assert_not_called()
    fake_browser.get_current_html.assert_called_once()
    assert result == fake_html


def test_fetch_html_invalid_url():
    fake_browser = MagicMock()
    with patch("app.tools.fetch_html.get_browser_manager", return_value=fake_browser):
        result = fetch_html.invoke({"url": "ftp://bad-scheme.com"})
    assert "fetch_html failed" in result
    fake_browser.navigate.assert_not_called()


def test_fetch_html_rejects_localhost():
    fake_browser = MagicMock()
    with patch("app.tools.fetch_html.get_browser_manager", return_value=fake_browser):
        result = fetch_html.invoke({"url": "http://localhost"})
    assert "fetch_html failed" in result
    fake_browser.navigate.assert_not_called()