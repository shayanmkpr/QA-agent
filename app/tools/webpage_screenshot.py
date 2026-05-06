from langchain_core.tools import tool

from infra.browser import get_browser_manager
from app.qa_utils import compress_image


@tool
def webpage_screenshot() -> str:
    """Take a full-page screenshot of the CURRENT page.
    Does NOT navigate — use navigate() first if you need to go to a URL.
    Returns a base64-encoded PNG data URI.
    """
    mgr = get_browser_manager()
    try:
        result = mgr.screenshot_current()
        if result.startswith("data:image"):
            result = compress_image(result)
        return result
    except RuntimeError as exc:
        return f"[webpage_screenshot failed: {exc}]"
