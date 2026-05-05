from langchain_core.tools import tool

from infra.browser import get_browser_manager
from app.tools._url import _validate_url


_MAX_HTML_CHARS = 100_000


@tool
def fetch_html(url: str = "") -> str:
    """Fetch and return the raw HTML content of a page. If a URL is given, navigates there first.
    Otherwise returns the HTML of the current page.

    Use this to inspect page structure, find selectors, or check content.
    """
    mgr = get_browser_manager()
    try:
        if url:
            _validate_url(url)
            mgr.navigate(url)
        html = mgr.get_current_html()
        if len(html) > _MAX_HTML_CHARS:
            print(f"[fetch_html] truncated {len(html):,} -> {_MAX_HTML_CHARS:,} chars")
            html = html[:_MAX_HTML_CHARS] + "\n\n[truncated]"
        else:
            print(f"[fetch_html] {len(html):,} chars (within limit)")
        return html
    except (RuntimeError, ValueError) as exc:
        return f"[fetch_html failed: {exc}]"
