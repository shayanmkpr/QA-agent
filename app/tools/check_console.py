from langchain_core.tools import tool

from infra.browser import get_browser_manager


@tool
def check_console_errors() -> str:
    """Check the browser console for JavaScript errors and warnings.

    Reports all console.error() and console.warn() messages that have been
    emitted since the last call (or since the page loaded).  The log is
    cleared after each call, so repeated calls only show new entries.

    Use this after any page interaction to validate that no unexpected
    JavaScript errors occurred.
    """
    mgr = get_browser_manager()
    try:
        return mgr.get_console_summary()
    except RuntimeError as exc:
        return f"[check_console_errors failed: {exc}]"
    except Exception as exc:
        return f"[check_console_errors failed: {exc}]"
