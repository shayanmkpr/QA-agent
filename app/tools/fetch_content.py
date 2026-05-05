from langchain_core.tools import tool

from infra.browser import get_browser_manager
from app.tools._url import _validate_url


@tool
def fetch_content(url: str = "") -> str:
    """Fetch readable text content (no HTML tags) of a page. If a URL is given, navigates there first.
    Otherwise returns the text of the current page.

    Use this when you want to read the actual page content, not raw markup.
    """
    mgr = get_browser_manager()
    try:
        if url:
            _validate_url(url)
            mgr.navigate(url)
        return mgr.get_current_text()
    except (RuntimeError, ValueError) as exc:
        return f"[fetch_content failed: {exc}]"
