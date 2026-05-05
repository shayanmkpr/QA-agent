"""Tests for app.tools.fetch_content"""

from unittest.mock import MagicMock, patch

from app.tools.fetch_content import fetch_content


def test_fetch_content_with_url():
    fake_text = "Hello, world!"
    fake_browser = MagicMock()
    fake_browser.get_current_text.return_value = fake_text

    with patch("app.tools.fetch_content.get_browser_manager", return_value=fake_browser):
        result = fetch_content.invoke({"url": "https://example.com"})

    fake_browser.navigate.assert_called_once_with("https://example.com")
    fake_browser.get_current_text.assert_called_once()
    assert result == fake_text


def test_fetch_content_no_url():
    fake_text = "Current page content"
    fake_browser = MagicMock()
    fake_browser.get_current_text.return_value = fake_text

    with patch("app.tools.fetch_content.get_browser_manager", return_value=fake_browser):
        result = fetch_content.invoke({})

    fake_browser.navigate.assert_not_called()
    fake_browser.get_current_text.assert_called_once()
    assert result == fake_text


def test_fetch_content_rejects_bad_url():
    fake_browser = MagicMock()
    with patch("app.tools.fetch_content.get_browser_manager", return_value=fake_browser):
        result = fetch_content.invoke({"url": "file:///etc/passwd"})
    assert "fetch_content failed" in result
    fake_browser.navigate.assert_not_called()