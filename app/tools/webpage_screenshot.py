from langchain_core.tools import tool

from infra.browser import get_browser_manager
from app.tools._url import _validate_url


@tool
def webpage_screenshot(url: str) -> str:
    """Open a URL in a headless browser and return a full-page screenshot as a base64-encoded PNG data URI.

    Use this when you need a complete screenshot of a specific webpage.
    The returned format matches the screen screenshot tool (data:image/png;base64,...)
    so it can be consumed by vision-capable models the same way.
    """
    _validate_url(url)
    return get_browser_manager().screenshot(url)
