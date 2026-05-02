"""Tests for app.tools.__init__ exports."""

from app.tools import (
    fetch_html,
    fetch_content,
    webpage_screenshot,
    screenshot,
)


def test_all_tools_are_importable():
    """Every exported tool should be a valid LangChain tool with an invoke method."""
    tools = [
        fetch_html,
        fetch_content,
        webpage_screenshot,
        screenshot,
    ]
    for tool in tools:
        assert hasattr(tool, "invoke"), f"{tool.name} is missing invoke()"
