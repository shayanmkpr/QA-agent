"""Tests for app.qa_utils"""

from unittest.mock import patch
from app.qa_utils import check_resources


def test_no_issues_on_healthy_page():
    """A page with self-referencing links and images should report no issues
    when every resource returns 200.
    """
    html = """
    <html>
      <body>
        <a href="https://example.com/about">About</a>
        <img src="https://example.com/logo.png">
        <link rel="stylesheet" href="https://example.com/style.css">
        <script src="https://example.com/app.js"></script>
      </body>
    </html>
    """

    with patch("app.qa_utils._check_resource") as mock_check:
        mock_check.return_value = (200, "")
        issues = check_resources(html, "https://example.com")

    assert len(issues) == 0


def test_broken_link_detected():
    """A 404 link should be reported as a backend issue."""
    html = '<a href="https://example.com/broken">Broken</a>'

    with patch("app.qa_utils._check_resource") as mock_check:
        def side_effect(url, timeout=10):
            if "broken" in url:
                return (404, "")
            return (200, "")

        mock_check.side_effect = side_effect
        issues = check_resources(html, "https://example.com")

    assert len(issues) == 1
    assert issues[0]["issue_type"] == "broken_link"
    assert issues[0]["description"] == "HTTP 404"
    assert issues[0]["category"] == "backend"


def test_broken_image_detected():
    """A failed image request should be reported."""
    html = '<img src="https://example.com/missing.png">'

    with patch("app.qa_utils._check_resource") as mock_check:
        mock_check.return_value = (0, "Connection refused")
        issues = check_resources(html, "https://example.com")

    assert len(issues) == 1
    assert issues[0]["issue_type"] == "broken_image"
    assert "Connection refused" in issues[0]["description"]
    assert issues[0]["category"] == "backend"


def test_missing_stylesheet_detected():
    """A 500 from a stylesheet should be flagged."""
    html = '<link rel="stylesheet" href="https://example.com/style.css">'

    with patch("app.qa_utils._check_resource") as mock_check:
        mock_check.return_value = (500, "")
        issues = check_resources(html, "https://example.com")

    assert len(issues) == 1
    assert issues[0]["issue_type"] == "missing_asset"
    assert "Stylesheet" in issues[0]["description"]
    assert issues[0]["category"] == "backend"
