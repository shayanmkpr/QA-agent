from langchain_core.tools import tool

from infra.browser import get_browser_manager
from app.tools._url import _validate_url
from app.qa_utils import compress_image


@tool
def webpage_screenshot(url: str = "") -> str:
    """Take a full-page screenshot. If a URL is given, navigates there first.
    Otherwise screenshots the current page. Returns a base64-encoded PNG data URI.
    """
    mgr = get_browser_manager()
    try:
        if url:
            _validate_url(url)
            mgr.navigate(url)
        result = mgr.screenshot_current()
        if result.startswith("data:image"):
            result = compress_image(result)
        return result
    except (RuntimeError, ValueError) as exc:
        return f"[webpage_screenshot failed: {exc}]"
