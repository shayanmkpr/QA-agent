from langchain_core.tools import tool

from infra.browser import get_browser_manager
import json


@tool
def scroll_down(amount: int = 600) -> str:
    """Scroll the browser page down by a given pixel amount (default 600px).
    Use this to see content below the fold that isn't visible in the current screenshot.
    Returns scroll position as JSON with keys: scroll_y, scrolled, at_bottom.
    When at_bottom is true, you've reached the end of the page.
    """
    mgr = get_browser_manager()
    try:
        info = mgr.scroll_down(amount)
        return f"[scroll_down] {json.dumps(info)}"
    except RuntimeError as exc:
        return f"[scroll_down failed: {exc}]"


@tool
def scroll_to_top() -> str:
    """Scroll back to the top of the browser page.
    Use this to reset your view before starting a new scan of the page.
    """
    mgr = get_browser_manager()
    try:
        info = mgr.scroll_to_top()
        return f"[scroll_to_top] {json.dumps(info)}"
    except RuntimeError as exc:
        return f"[scroll_to_top failed: {exc}]"