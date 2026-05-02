from langchain_core.tools import tool

from infra.browser import get_browser_manager


@tool
def fetch_content(url: str) -> str:  # FIXME: No URL validation; allows file://, internal hosts.
    """Fetch a URL and return its extracted readable text content (no HTML tags).

    Use this when you want to read the actual page content, not raw markup.
    """
    return get_browser_manager().get_text(url)
