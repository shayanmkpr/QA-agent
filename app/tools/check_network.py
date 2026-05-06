from langchain_core.tools import tool

from infra.browser import get_browser_manager


@tool
def check_network() -> str:
    """Check the browser network log for failed requests, error HTTP
    responses (4xx / 5xx), and slow requests (> 3 seconds).

    Reports issues that have occurred since the last call (or since the
    page loaded).  The log is cleared after each call — repeated calls
    only show new entries.

    Use this after navigating or interacting to catch broken APIs,
    missing assets, and slow endpoints.
    """
    mgr = get_browser_manager()
    try:
        return mgr.get_network_summary()
    except RuntimeError as exc:
        return f"[check_network failed: {exc}]"
    except Exception as exc:
        return f"[check_network failed: {exc}]"
