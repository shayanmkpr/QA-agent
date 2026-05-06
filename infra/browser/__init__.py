from typing import Optional

from infra.browser._session import (
    _init,
    _ensure_ready,
    _ensure_context,
    get_page,
    clear_context,
    close,
    _enter,
    _exit,
)
from infra.browser._navigation import navigate, click, fill_fields, hover
from infra.browser._extraction import get_current_html, get_current_text, screenshot_current
from infra.browser._scrolling import scroll_down, scroll_to_top
from infra.browser._monitoring import get_console_summary, get_network_summary


class BrowserManager:
    """Manages a headless Playwright browser with a persistent page for stateful interaction."""

    __init__ = _init
    _ensure_ready = _ensure_ready
    _ensure_context = _ensure_context
    get_page = get_page
    navigate = navigate
    click = click
    fill_fields = fill_fields
    hover = hover
    get_current_html = get_current_html
    get_current_text = get_current_text
    screenshot_current = screenshot_current
    scroll_down = scroll_down
    scroll_to_top = scroll_to_top
    get_console_summary = get_console_summary
    get_network_summary = get_network_summary
    clear_context = clear_context
    close = close
    __enter__ = _enter
    __exit__ = _exit


_browser_manager: Optional[BrowserManager] = None


def get_browser_manager() -> BrowserManager:
    global _browser_manager
    if _browser_manager is None:
        _browser_manager = BrowserManager()
    return _browser_manager
