"""Tests for app.tools.screenshot"""

from unittest.mock import MagicMock, patch

from app.tools.screenshot import screenshot


def test_screenshot_returns_data_uri():
    """screenshot should return a base64-encoded PNG data URI."""
    fake_img = MagicMock()
    fake_img.save = MagicMock()

    with patch("app.tools.screenshot.ImageGrab.grab", return_value=fake_img):
        with patch("app.tools.screenshot.base64.b64encode", return_value=b"FAKEB64="):
            with patch("app.tools.screenshot.io.BytesIO"):
                result = screenshot.invoke({})

    # The function always returns a data URI starting with data:image/png;base64,
    assert result.startswith("data:image/png;base64,")


def test_screenshot_returns_error_on_permission_denied():
    """If ImageGrab raises OSError, a helpful error string is returned."""
    with patch(
        "app.tools.screenshot.ImageGrab.grab",
        side_effect=OSError("Screen capture denied"),
    ):
        result = screenshot.invoke({})

    assert "screenshot failed" in result
    assert "Screen Recording permission" in result
