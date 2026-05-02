"""Tests for app.tools.fetch_content"""

from unittest.mock import MagicMock, patch

from app.tools.fetch_content import fetch_content


def test_fetch_content_valid_url():
    """fetch_content should call the browser manager and return extracted text."""
    fake_text = "Hello, world!"
    fake_browser = MagicMock()
    fake_browser.get_text.return_value = fake_text

    with patch("app.tools.fetch_content.get_browser_manager", return_value=fake_browser):
        result = fetch_content.invoke({"url": "https://example.com"})

    fake_browser.get_text.assert_called_once_with("https://example.com")
    assert result == fake_text


def test_fetch_content_rejects_bad_url():
    """A non-HTTP URL should raise ValueError."""
    with patch("app.tools.fetch_content.get_browser_manager") as mock_bm:
        import pytest

        with pytest.raises(ValueError):
            fetch_content.invoke({"url": "file:///etc/passwd"})
        mock_bm.assert_not_called()
