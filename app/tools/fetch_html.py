from langchain_core.tools import tool

from infra.browser import get_browser_manager

_MAX_HTML_CHARS = 100_000


@tool
def fetch_html() -> str:
    """Fetch and return the raw HTML content of the CURRENT page.
    Use this to inspect page structure, find selectors, or check content.
    Does NOT navigate — use navigate() first if you need to go to a URL.
    """
    mgr = get_browser_manager()
    try:
        html = mgr.get_current_html()
        if len(html) > _MAX_HTML_CHARS:
            print(f"[fetch_html] truncated {len(html):,} -> {_MAX_HTML_CHARS:,} chars")
            html = html[:_MAX_HTML_CHARS] + "\n\n[truncated]"
        else:
            print(f"[fetch_html] {len(html):,} chars (within limit)")
        return html
    except RuntimeError as exc:
        return f"[fetch_html failed: {exc}]"
