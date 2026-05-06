# BrowserManager

Manages a headless Playwright Chromium browser singleton. A single browser, context, and page persist across all tool calls — cookies, localStorage, and login state carry from one interaction to the next.

## Architecture

```
sync_playwright().start()          → _pw
  └─ launcher.launch()             → _browser (chromium)
       └─ browser.new_context()    → _context
            └─ context.new_page()  → _page (persistent)
```

Everything is created lazily — nothing launches at `__init__()`. The first call that needs a page triggers the full chain.

## Singleton

```python
_browser_manager: Optional[BrowserManager] = None

def get_browser_manager() -> BrowserManager:
    global _browser_manager
    if _browser_manager is None:
        _browser_manager = BrowserManager()
    return _browser_manager
```

All tool calls within the same process share the same browser instance.

## Public API

### Navigation & interaction

| Method | What it does |
|---|---|
| `navigate(url) → str` | Go to URL, wait for `networkidle`. Returns final URL. |
| `click(selector) → str` | Click element matching selector, wait for `networkidle`. Returns URL. |
| `fill_fields(data, submit_selector="") → str` | Fill form fields (`{selector: value}`). Clicks submit_selector or presses Enter on last field. Returns URL. |

### Page inspection

| Method | What it does |
|---|---|
| `get_current_html() → str` | Full HTML via `page.content()` |
| `get_current_text() → str` | Visible text. Strips `<script>`, `<style>`, `<nav>`, `<footer>`, `<header>`, `<aside>` via BeautifulSoup. |
| `screenshot_current() → str` | Full-page PNG screenshot as `data:image/png;base64,...` |
| `scroll_down(amount=600) → dict` | Waits for `networkidle`, then `window.scrollTo(0, current + amount)`. Returns `{scroll_y, scrolled, at_bottom}`. |
| `scroll_to_top() → dict` | `window.scrollTo(0, 0)`. Returns `{scroll_y: 0, scrolled: "to_top", at_bottom: False}`. |

### Session management

| Method | What it does |
|---|---|
| `clear_context() → None` | Closes page + context (cookies/storage wiped). Browser stays alive. Next `get_page()` creates fresh context+page. |
| `close() → None` | Full teardown: clear_context + close browser + stop Playwright. All state reset to `None`. |
| `get_page()` | Returns current Playwright `Page`, creating if needed. Raises `RuntimeError` on failure. |

## Error handling

`_ensure_ready()` and `_ensure_context()` return `None` on success or an error **string** on failure (no exceptions). `get_page()` is the boundary — it calls the `_ensure_*` chain and raises `RuntimeError` if any step returned an error.

Cleanup methods (`clear_context`, `close`) suppress all exceptions — teardown is best-effort.
