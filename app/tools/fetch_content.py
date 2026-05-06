from langchain_core.tools import tool

from infra.browser import get_browser_manager


@tool
def fetch_content() -> str:
    """Fetch readable text content (no HTML tags) of the CURRENT page.
    Use this when you want to read what's on the page right now.
    Does NOT navigate — use navigate() first if you need to go to a URL.
    """
    mgr = get_browser_manager()
    try:
        return mgr.get_current_text()
    except RuntimeError as exc:
        return f"[fetch_content failed: {exc}]"
