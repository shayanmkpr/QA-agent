from infra.logging import _log


def scroll_down(self, amount: int = 600) -> dict:
    page = self.get_page()
    page.wait_for_load_state("networkidle", timeout=10_000)
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
