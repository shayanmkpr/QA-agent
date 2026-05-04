from langchain_core.tools import tool

from infra.browser import get_browser_manager
from app.tools._url import _validate_url


_MAX_HTML_CHARS = 100_000


@tool
def fetch_html(url: str) -> str:
    """Fetch and return the raw HTML content of a given URL using a headless browser."""
    _validate_url(url)
    html = get_browser_manager().get_html(url)
    if len(html) > _MAX_HTML_CHARS:
        print(f"[fetch_html] truncated {len(html):,} -> {_MAX_HTML_CHARS:,} chars")
        html = html[:_MAX_HTML_CHARS] + "\n\n[truncated]"
    else:
        print(f"[fetch_html] {len(html):,} chars (within limit)")
    return html
