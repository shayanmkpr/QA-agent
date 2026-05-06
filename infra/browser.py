import base64
import time
from typing import Optional

from bs4 import BeautifulSoup

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None  # type: ignore

from infra.logging import _log


class BrowserManager:
    """Manages a headless Playwright browser with a persistent page for stateful interaction."""

    def __init__(self, browser_type: str = "chromium"):
        self.browser_type = browser_type
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None

    def _ensure_ready(self) -> Optional[str]:
        """Returns an error message if the browser cannot be used."""
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
                self._browser = launcher.launch()
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
        return self._page

    def navigate(self, url: str) -> str:
        _log("[browser]", f"navigating to {url}…")
        page = self.get_page()
        start = time.time()
        page.goto(url, wait_until="networkidle")
        _log("[browser]", f"  loaded {page.url} ({time.time() - start:.1f}s)", title=page.title())
        return page.url

    def click(self, selector: str) -> str:
        _log("[browser]", f"clicking {selector}…")
        page = self.get_page()
        start = time.time()
        page.click(selector)
        page.wait_for_load_state("networkidle")
        _log("[browser]", f"  now at {page.url} ({time.time() - start:.1f}s)")
        return page.url

    def fill_fields(self, data: dict, submit_selector: str = "") -> str:
        _log("[browser]", f"filling {len(data)} field(s)", selectors=list(data.keys()))
        page = self.get_page()
        start = time.time()
        selectors = list(data.keys())
        for sel in selectors:
            page.fill(sel, data[sel])
        if submit_selector:
            page.click(submit_selector)
        else:
            page.press(selectors[-1], "Enter")
        page.wait_for_load_state("networkidle")
        _log("[browser]", f"  submitted, now at {page.url} ({time.time() - start:.1f}s)")
        return page.url

    def get_current_html(self) -> str:
        start = time.time()
        html = self.get_page().content()
        _log("[browser]", f"fetched HTML: {len(html)} chars ({time.time() - start:.1f}s)")
        return html

    def get_current_text(self) -> str:
        start = time.time()
        html = self.get_current_html()
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        lines = (line.strip() for line in text.splitlines())
        result = "\n".join(line for line in lines if line)
        _log("[browser]", f"extracted text: {len(result)} chars ({time.time() - start:.1f}s)")
        return result

    def screenshot_current(self) -> str:
        _log("[browser]", "taking full-page screenshot…")
        start = time.time()
        page = self.get_page()
        png_bytes = page.screenshot(full_page=True)
        b64 = base64.b64encode(png_bytes).decode("utf-8")
        elapsed = time.time() - start
        _log("[browser]", f"  screenshot done: {len(b64)//1024}KB base64 ({elapsed:.1f}s)")
        return f"data:image/png;base64,{b64}"

    def scroll_down(self, amount: int = 600) -> dict:
        page = self.get_page()
        page.wait_for_load_state("networkidle")
        current = page.evaluate("window.scrollY")
        page.evaluate(f"window.scrollTo(0, {current + amount})")
        new_y = page.evaluate("window.scrollY")
        at_bottom = page.evaluate(
            "window.scrollY + window.innerHeight >= document.body.scrollHeight - 10"
        )
        _log("[browser]", f"scrolled {amount}px: {current} -> {new_y}", at_bottom=at_bottom)
        return {"scroll_y": new_y, "scrolled": new_y - current, "at_bottom": at_bottom}

    def scroll_to_top(self) -> dict:
        page = self.get_page()
        page.evaluate("window.scrollTo(0, 0)")
        _log("[browser]", "scrolled to top")
        return {"scroll_y": 0, "scrolled": "to_top", "at_bottom": False}

    def clear_context(self) -> None:
        _log("[browser]", "clearing browser context (cookies/storage/page)")
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

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


_browser_manager: Optional[BrowserManager] = None


def get_browser_manager() -> BrowserManager:
    global _browser_manager
    if _browser_manager is None:
        _browser_manager = BrowserManager()
    return _browser_manager