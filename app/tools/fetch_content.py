from langchain_core.tools import tool

from infra.browser import get_browser_manager
from app.tools._url import _validate_url


@tool
def fetch_content(url: str) -> str:
    """Fetch a URL and return its extracted readable text content (no HTML tags).

    Use this when you want to read the actual page content, not raw markup.
    """
    _validate_url(url)
    return get_browser_manager().get_text(url)
