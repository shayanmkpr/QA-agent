from langchain_core.tools import tool

from app.tools._url import _validate_url
from infra.browser import get_browser_manager


@tool
def navigate(url: str) -> str:
    """Navigate the persistent browser to a URL. Use this first before interacting with a page.

    Returns the current URL and page title after navigation.
    """
    _validate_url(url)
    mgr = get_browser_manager()
    try:
        mgr.navigate(url)
        page = mgr.get_page()
        return f"[navigate] now at {page.url} (title: {page.title()})"
    except RuntimeError as exc:
        return f"[navigate failed: {exc}]"
