import base64
from typing import Optional

from bs4 import BeautifulSoup

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None  # type: ignore


class BrowserManager:
    """Manages a headless Playwright browser (default: Chromium) for page interaction."""

    def __init__(self, browser_type: str = "playwright"):
        self.browser_type = browser_type
        self._pw = None
        self._browser = None

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

    def screenshot(self, url: str) -> str:
        """Return a full-page screenshot as a base64 PNG data URI."""
        err = self._ensure_ready()
        if err:
            return f"[webpage_screenshot failed: {err}]"

        page = self._browser.new_page()
        try:
            page.goto(url, wait_until="networkidle")
            png_bytes = page.screenshot(full_page=True)
        except Exception as exc:
            return f"[webpage_screenshot failed: {exc}]"
        finally:
            page.close()

        b64 = base64.b64encode(png_bytes).decode("utf-8")
        return f"data:image/png;base64,{b64}"

    def get_html(self, url: str) -> str:
        """Return the raw HTML of a page."""
        err = self._ensure_ready()
        if err:
            return f"[get_html failed: {err}]"

        page = self._browser.new_page()
        try:
            page.goto(url, wait_until="networkidle")
            html = page.content()
        except Exception as exc:
            return f"[get_html failed: {exc}]"
        finally:
            page.close()
        return html

    def get_text(self, url: str) -> str:
        """Return visible text extracted from a page (no tags, no scripts)."""
        html = self.get_html(url)
        if html.startswith("[get_html failed:"):
            return html

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        lines = (line.strip() for line in text.splitlines())
        return "\n".join(line for line in lines if line)

    def close(self) -> None:
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._pw:
            self._pw.stop()
            self._pw = None

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
