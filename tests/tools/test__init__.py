"""Tests for app.tools.__init__ exports."""

from app.tools import (
    navigate,
    click_link,
    fill_form,
    fetch_html,
    fetch_content,
    webpage_screenshot,
    screenshot,
    write_report,
    clear_session,
)


def test_all_tools_are_importable():
    """Every exported tool should be a valid LangChain tool with an invoke method."""
    tools = [
        navigate,
        click_link,
        fill_form,
        fetch_html,
        fetch_content,
        webpage_screenshot,
        screenshot,
        write_report,
        clear_session,
    ]
    for tool in tools:
        assert hasattr(tool, "invoke"), f"{tool.name} is missing invoke()"