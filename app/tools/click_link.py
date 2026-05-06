from langchain_core.tools import tool

from infra.browser import get_browser_manager


@tool
def click_link(selector: str, text: str = "") -> str:
    """Click an element on the current page. Use AFTER navigating to a page.

    Parameters:
    - selector: A Playwright selector. Supports:
      * CSS: 'button', '.class', '#id', 'a[href="/login"]', 'button.primary'
      * Text-based: 'text=Login', 'button:has-text("Sign In")', '[aria-label="Menu"]'
      * DO NOT use jQuery selectors like :contains() — they are NOT supported.
    - text (optional): If provided, clicks the element matching selector that
      contains this text. E.g. selector='button', text='Login' clicks a
      button whose text includes "Login".

    Returns the URL and page title after the click.
    """
    mgr = get_browser_manager()
    try:
        if text:
            selector = f"{selector}:has-text({text!r})"
        mgr.click(selector)
        page = mgr.get_page()
        return f"[click_link] clicked '{selector}', now at {page.url} (title: {page.title()})"
    except RuntimeError as exc:
        return f"[click_link failed: {exc}]"
    except Exception as exc:
        return f"[click_link failed: {exc}]"
