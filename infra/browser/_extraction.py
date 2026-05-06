import base64
import time

from bs4 import BeautifulSoup

from infra.logging import _log


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
