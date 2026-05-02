from langchain_core.tools import tool

from infra.browser import get_browser_manager
from app.tools._url import _validate_url


@tool
def fetch_html(url: str) -> str:
    """Fetch and return the raw HTML content of a given URL using a headless browser."""
    _validate_url(url)
    return get_browser_manager().get_html(url)
