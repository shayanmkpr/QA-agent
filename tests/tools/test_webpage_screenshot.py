"""Tests for app.tools.webpage_screenshot"""

from unittest.mock import MagicMock, patch

from app.tools.webpage_screenshot import webpage_screenshot


def test_webpage_screenshot_valid_url():
    fake_data_uri = "data:image/png;base64,iVBORw0KGgo="
    fake_browser = MagicMock()
    fake_browser.screenshot_current.return_value = fake_data_uri

    with patch(
        "app.tools.webpage_screenshot.get_browser_manager", return_value=fake_browser
    ), patch("app.tools.webpage_screenshot.compress_image", return_value=fake_data_uri):
        result = webpage_screenshot.invoke({"url": "https://example.com"})

    fake_browser.navigate.assert_called_once_with("https://example.com")
    fake_browser.screenshot_current.assert_called_once()
    assert result == fake_data_uri


def test_webpage_screenshot_rejects_localhost():
    fake_browser = MagicMock()
    with patch("app.tools.webpage_screenshot.get_browser_manager", return_value=fake_browser):
        result = webpage_screenshot.invoke({"url": "http://127.0.0.1"})
    assert "webpage_screenshot failed" in result
    fake_browser.navigate.assert_not_called()