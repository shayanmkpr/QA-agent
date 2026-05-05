from langchain_core.tools import tool

from app.tools._url import _validate_url
from infra.browser import get_browser_manager


@tool
def click_link(url: str, selector: str) -> str:
    """Navigate to a URL and click an element matching a CSS selector.

    Returns the URL and page title after the click.
    Use this for clicking buttons, links, or any clickable element.
    """
    _validate_url(url)
    mgr = get_browser_manager()
    err = mgr._ensure_ready()
    if err:
        return f"[click_link failed: {err}]"

    page = mgr._browser.new_page()
    try:
        page.goto(url, wait_until="networkidle")
        page.click(selector)
        page.wait_for_load_state("networkidle")
        return f"[click_link] clicked '{selector}' on {url}, now at {page.url} (title: {page.title()})"
    except Exception as exc:
        return f"[click_link failed: {exc}]"
    finally:
        page.close()
