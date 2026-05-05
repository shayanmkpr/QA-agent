from langchain_core.tools import tool

from infra.browser import get_browser_manager


@tool
def clear_session() -> str:
    """Clear the browser session — closes the current page and clears cookies/storage.
    Use this to log out or start a fresh session for testing."""
    get_browser_manager().clear_context()
    return "[clear_session] browser session cleared"
