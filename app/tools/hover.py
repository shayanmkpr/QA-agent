from langchain_core.tools import tool

from infra.browser import get_browser_manager


@tool
def hover(selector: str) -> str:
    """Hover the mouse cursor over an element on the current page.

    Use this to reveal hidden UI such as tooltips, dropdown menus,
    hover cards, or expandable sections that only appear on mouse-over.

    Parameters:
    - selector: A Playwright CSS selector for the element to hover over.

    Returns the current URL after hovering.
    """
    mgr = get_browser_manager()
    try:
        mgr.hover(selector)
        page = mgr.get_page()
        return f"[hover] hovered '{selector}', still at {page.url} (title: {page.title()})"
    except RuntimeError as exc:
        return f"[hover failed: {exc}]"
    except Exception as exc:
        return f"[hover failed: {exc}]"
