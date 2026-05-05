import json

from langchain_core.tools import tool

from infra.browser import get_browser_manager


@tool
def fill_form(fields: str, submit_selector: str = "") -> str:
    """Fill form fields on the current page. Use this AFTER navigating to a page with a form.

    `fields` is a JSON string mapping CSS selectors to values, e.g.:
    '{"input[name=\\"email\\"]": "user@example.com", "input[name=\\"password\\"]": "secret"}'

    `submit_selector` is an optional CSS selector for the submit button.
    If provided, clicks it to submit. Otherwise presses Enter on the last field.
    Returns the landing URL and page title.
    """
    mgr = get_browser_manager()
    try:
        data = json.loads(fields)
        mgr.fill_fields(data, submit_selector)
        page = mgr.get_page()
        return f"[fill_form] filled {len(data)} field(s), now at {page.url} (title: {page.title()})"
    except RuntimeError as exc:
        return f"[fill_form failed: {exc}]"
    except Exception as exc:
        return f"[fill_form failed: {exc}]"
