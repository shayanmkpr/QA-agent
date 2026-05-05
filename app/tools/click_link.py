from langchain_core.tools import tool

from infra.browser import get_browser_manager


@tool
def click_link(selector: str) -> str:
    """Click an element on the current page matching a CSS selector.

    Use this AFTER navigating to a page. Returns the URL and page title after the click.
    Use this for clicking buttons, links, or any clickable element.
    """
    mgr = get_browser_manager()
    try:
        mgr.click(selector)
        page = mgr.get_page()
        return f"[click_link] clicked '{selector}', now at {page.url} (title: {page.title()})"
    except RuntimeError as exc:
        return f"[click_link failed: {exc}]"
    except Exception as exc:
        return f"[click_link failed: {exc}]"
