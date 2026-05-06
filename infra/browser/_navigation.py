import time

from infra.logging import _log

_NETWORK_IDLE_TIMEOUT = 10_000
_SPA_NAV_WAIT = 2_000


def _wait_after_action(self, page, old_url: str, start: float):
    try:
        page.wait_for_load_state("networkidle", timeout=_NETWORK_IDLE_TIMEOUT)
    except Exception:
        page.wait_for_timeout(_SPA_NAV_WAIT)
    if page.url == old_url:
        page.wait_for_timeout(1_000)
    _log("[browser]", f"  now at {page.url} ({time.time() - start:.1f}s)")


def navigate(self, url: str) -> str:
    _log("[browser]", f"navigating to {url}…")
    page = self.get_page()
    start = time.time()
    try:
        page.goto(url, wait_until="networkidle", timeout=_NETWORK_IDLE_TIMEOUT)
    except Exception:
        page.wait_for_timeout(_SPA_NAV_WAIT)
    _log("[browser]", f"  loaded {page.url} ({time.time() - start:.1f}s)", title=page.title())
    return page.url


def click(self, selector: str) -> str:
    _log("[browser]", f"clicking {selector}…")
    page = self.get_page()
    start = time.time()
    old_url = page.url
    page.click(selector)
    _wait_after_action(self, page, old_url, start)
    return page.url


def fill_fields(self, data: dict, submit_selector: str = "") -> str:
    _log("[browser]", f"filling {len(data)} field(s)", selectors=list(data.keys()))
    page = self.get_page()
    start = time.time()
    old_url = page.url
    selectors = list(data.keys())
    for sel in selectors:
        page.fill(sel, data[sel])
    if submit_selector:
        page.click(submit_selector)
    else:
        page.press(selectors[-1], "Enter")
    _wait_after_action(self, page, old_url, start)
    return page.url


def hover(self, selector: str) -> str:
    """Hover the mouse over an element (for tooltips, dropdowns, hover states)."""
    _log("[browser]", f"hovering {selector}…")
    page = self.get_page()
    page.hover(selector)
    page.wait_for_timeout(500)
    return page.url
