"""Tests for app.tools.webpage_screenshot"""

from unittest.mock import MagicMock, patch

from app.tools.webpage_screenshot import webpage_screenshot


def test_webpage_screenshot_valid_url():
    """webpage_screenshot should call the browser manager and return a data URI."""
    fake_data_uri = "data:image/png;base64,iVBORw0KGgo="
    fake_browser = MagicMock()
    fake_browser.screenshot.return_value = fake_data_uri

    with patch(
        "app.tools.webpage_screenshot.get_browser_manager", return_value=fake_browser
    ):
        result = webpage_screenshot.invoke({"url": "https://example.com"})

    fake_browser.screenshot.assert_called_once_with("https://example.com")
    assert result == fake_data_uri


def test_webpage_screenshot_rejects_localhost():
    """Localhost must be rejected before the browser is touched."""
    with patch("app.tools.webpage_screenshot.get_browser_manager") as mock_bm:
        import pytest

        with pytest.raises(ValueError, match="internal"):
            webpage_screenshot.invoke({"url": "http://127.0.0.1"})
        mock_bm.assert_not_called()
