from typing import Optional

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

from infra.logging import _log
from infra.browser._monitoring import _setup_monitoring


def _init(self, browser_type: str = "chromium", headless: bool = True, slow_mo: int = 0) -> None:
    self.browser_type = browser_type
    self.headless = headless
    self.slow_mo = slow_mo
    self._pw = None
    self._browser = None
    self._context = None
    self._page = None
    self._console_log: list = []
    self._network_log: list = []


def _ensure_ready(self) -> Optional[str]:
    if sync_playwright is None:
        return (
            "Playwright is not installed.\n"
            "Please run: pip install playwright && playwright install chromium"
        )
    if self._pw is None:
        try:
            self._pw = sync_playwright().start()
        except Exception as exc:
            return f"Failed to start Playwright: {exc}"
    if self._browser is None:
        try:
            launcher = getattr(self._pw, self.browser_type)
            self._browser = launcher.launch(
                headless=self.headless,
                slow_mo=self.slow_mo,
            )
        except Exception as exc:
            return (
                f"{self.browser_type} browser not found.\n\n"
                f"Failed to launch browser: {exc}\n\n"
                "Install it? Run: playwright install chromium"
            )
    return None


def _ensure_context(self) -> Optional[str]:
    err = self._ensure_ready()
    if err:
        return err
    if self._context is None:
        self._context = self._browser.new_context()
    return None


def get_page(self):
    err = self._ensure_context()
    if err:
        raise RuntimeError(err)
    if self._page is None:
        self._page = self._context.new_page()
        _setup_monitoring(self._page, self._console_log, self._network_log)
    return self._page


def clear_context(self) -> None:
    _log("[browser]", "clearing browser context (cookies/storage/page)")
    self._console_log.clear()
    self._network_log.clear()
    if self._page:
        try:
            self._page.close()
        except Exception:
            pass
        self._page = None
    if self._context:
        try:
            self._context.close()
        except Exception:
            pass
        self._context = None


def close(self) -> None:
    self.clear_context()
    b, pw = self._browser, self._pw
    self._browser = None
    self._pw = None
    try:
        if b:
            b.close()
    except Exception:
        pass
    try:
        if pw:
            pw.stop()
    except Exception:
        pass


def _enter(self):
    return self


def _exit(self, exc_type, exc_val, exc_tb):
    self.close()
    return False
