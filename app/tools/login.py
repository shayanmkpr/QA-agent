from langchain_core.tools import tool

from app.tools._url import _validate_url
from infra.browser import get_browser_manager


@tool
def login(url: str, username: str, password: str) -> str:
    """Navigate to a login page, fill in username and password, click submit, and report the result.

    The tool automatically detects common username/password fields and the submit button.
    Returns the URL and page title after submission so you can confirm login success.
    """
    _validate_url(url)
    return get_browser_manager().login(url, username, password)
