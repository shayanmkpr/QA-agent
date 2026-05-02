from langchain_core.tools import tool

from infra.browser import get_browser_manager


@tool
def fetch_html(url: str) -> str:  # FIXME: No URL validation; allows file://, internal hosts.
    """Fetch and return the raw HTML content of a given URL using a headless browser."""
    return get_browser_manager().get_html(url)
