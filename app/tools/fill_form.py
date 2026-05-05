from langchain_core.tools import tool

from app.tools._url import _validate_url
from infra.browser import get_browser_manager


@tool
def fill_form(url: str, fields: str) -> str:
    """Navigate to a URL and fill in form fields using CSS selectors.

    `fields` is a JSON string mapping CSS selectors to values, e.g.:
    '{"input[name=\\"email\\"]": "user@example.com", "input[name=\\"password\\"]": "secret"}'

    Submits the form by pressing Enter on the last field. Returns the landing URL and page title.
    """
    import json

    _validate_url(url)
    mgr = get_browser_manager()
    err = mgr._ensure_ready()
    if err:
        return f"[fill_form failed: {err}]"

    page = mgr._browser.new_page()
    try:
        page.goto(url, wait_until="networkidle")

        data = json.loads(fields)
        selectors = list(data.keys())
        for i, sel in enumerate(selectors):
            page.fill(sel, data[sel])
            if i == len(selectors) - 1:
                page.press(sel, "Enter")

        page.wait_for_load_state("networkidle")
        return f"[fill_form] filled {len(data)} field(s) on {url}, now at {page.url} (title: {page.title()})"
    except Exception as exc:
        return f"[fill_form failed: {exc}]"
    finally:
        page.close()
