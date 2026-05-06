# BrowserManager

`BrowserManager` manages a single headless Playwright browser instance that persists across tool calls, preserving cookies, localStorage, and login state throughout a QA session. It follows a browser → context → page hierarchy, exposing a persistent page for all interactions.

## Architecture

A single `BrowserManager` instance owns exactly one browser, one context, and one page at a time:

```
sync_playwright().start()          → _pw
  └─ launcher.launch()             → _browser (chromium by default)
       └─ browser.new_context()    → _context
            └─ context.new_page()  → _page (the persistent page)
```

**Session persistence**: Because `_browser`, `_context`, and `_page` are kept alive across calls to `navigate()`, `click()`, `fill_fields()`, etc., any cookies set by the server, localStorage mutations from JavaScript, or authenticated sessions survive. A login performed during one tool call carries into the next without re-authentication. This is the central design motivation — QA flows (login → navigate → assert → logout) require state continuity.

**Key design choices**:
- **Headless by default.** Playwright's `launch()` operates headless unless overridden via environment variables (`PLAYWRIGHT_HEADLESS=false` or similar) — handled by Playwright internals, not `BrowserManager`.
- **`wait_until="networkidle"`** on every `goto`, `click`, and `fill_fields` call. This ensures the page has settled (no outstanding network requests for 500ms) before returning control.

## Lifecycle

All resources are created lazily. No browser process launches at `__init__()` time — only when the first call that requires a page is made.

| Method | Guards / Behavior |
|---|---|
| `_ensure_ready()` | Checks `sync_playwright` is importable. Starts `sync_playwright().start()` if `_pw is None`. Launches the browser if `_browser is None`. Returns `None` on success, an error string on failure. |
| `_ensure_context()` | Calls `_ensure_ready()` first. Creates `_browser.new_context()` if `_context is None`. Returns error string or `None`. |
| `get_page()` | Calls `_ensure_context()` first. Creates `_context.new_page()` if `_page is None`. Returns the `Page` object. **Raises `RuntimeError`** if any prior step failed. |
| `clear_context()` | Closes `_page` then `_context` (suppresses exceptions on both), sets both to `None`. The browser process stays alive; the next `get_page()` call creates a fresh context and page — equivalent to a logout. |
| `close()` | Calls `clear_context()`, then closes `_browser` and stops `_pw`. Sets all internal references to `None`. Any subsequent call restarts the full chain from `_ensure_ready`. |

**Lazy creation flow** for a typical `navigate()` call:

1. `navigate()` calls `get_page()`.
2. `get_page()` calls `_ensure_context()`.
3. `_ensure_context()` calls `_ensure_ready()`.
4. `_ensure_ready()` starts Playwright and launches the browser if needed.
5. `_ensure_context()` creates the context if needed.
6. `get_page()` creates the page if needed.
7. `page.goto(url, wait_until="networkidle")` is called.

On subsequent calls to `navigate()` or any other page-dependent method, steps 3–6 are no-ops because `_pw`, `_browser`, `_context`, and `_page` are already set.

## Public API

### Core methods (operate on the persistent page)

- **`navigate(url: str) → str`** — Navigates the persistent page to `url` and waits for network idle. Returns the final page URL (useful for detecting redirects).
- **`click(selector: str) → str`** — Clicks the element matching `selector`, waits for network idle, returns the current URL.
- **`fill_fields(data: dict, submit_selector: str = "") → str`** — Fills form fields using `page.fill()` for each key-value pair in `data` (key = CSS selector, value = text). If `submit_selector` is provided, clicks that element to submit the form; otherwise presses `Enter` on the last field. Waits for network idle and returns the resulting URL.
- **`get_current_html() → str`** — Returns the full HTML of the persistent page via `page.content()`.
- **`get_current_text() → str`** — Extracts visible text from the persistent page. Strips `<script>`, `<style>`, `<nav>`, `<footer>`, `<header>`, and `<aside>` elements via BeautifulSoup, then returns deduplicated non-empty lines.
- **`screenshot_current() → str`** — Takes a full-page PNG screenshot (full_page=True) and returns it as a `data:image/png;base64,...` data URI string.
- **`scroll_down(amount: int = 600) → dict`** — Scrolls the page down by `amount` pixels using `window.scrollBy`. Returns `{scroll_y, scrolled, at_bottom}` where `at_bottom` is true when the viewport has reached the document bottom. Used by the agent to scan long pages section by section.
- **`scroll_to_top() → dict`** — Scrolls to the top of the page via `window.scrollTo(0,0)`. Returns `{scroll_y: 0, scrolled: "to_top", at_bottom: false}`.

### Backward-compatibility wrappers (navigate then act)

These exist for legacy tool signatures that pass a URL with every call. Each navigates to the provided URL and then delegates to the corresponding `_current` method:

- **`screenshot(url: str) → str`** — `navigate(url)` → `screenshot_current()`
- **`get_html(url: str) → str`** — `navigate(url)` → `get_current_html()`
- **`get_text(url: str) → str`** — `navigate(url)` → `get_current_text()`

### Session management

- **`clear_context() → None`** — Destroys the current context and page. The page reference is garbage-collected; the next `get_page()` call creates a brand-new context and page. Use this to simulate logout or start a fresh session without restarting the browser.
- **`close() → None`** — Full teardown: calls `clear_context()`, then closes the browser and stops the Playwright driver. Internal state is reset to `None`.

### Accessor

- **`get_page()`** — Returns the current Playwright `Page` object, creating it if necessary. Raises `RuntimeError` with a descriptive message if Playwright is not installed or the browser fails to launch.

### Context manager support

`BrowserManager` implements `__enter__` and `__exit__`, so it can be used as a context manager. `__exit__` calls `close()` and returns `False` (does not suppress exceptions).

## Singleton

```python
_browser_manager: Optional[BrowserManager] = None

def get_browser_manager() -> BrowserManager:
    global _browser_manager
    if _browser_manager is None:
        _browser_manager = BrowserManager()
    return _browser_manager
```

`get_browser_manager()` returns a module-level singleton. All tool calls within the same process share the same `BrowserManager` instance and therefore the same browser, context, and page. This is how session persistence works across tool invocations: each call to a MCP tool or agent action that imports and calls `get_browser_manager()` gets the same persistent browser state.

## Error Handling

`_ensure_ready()` and `_ensure_context()` follow a consistent error-reporting convention: they return `None` on success or a human-readable error **string** on failure. They do not raise exceptions.

The boundary between error-return and exception-raise is `get_page()`: it calls the `_ensure_*` chain and, if any step returns an error string, raises `RuntimeError(err)`. This means all public methods that call `get_page()` (i.e., every public method except `clear_context()` and `close()`) can raise `RuntimeError`.

`clear_context()` and `close()` suppress exceptions during cleanup — a partially-initialized browser or context that fails to close does not propagate to the caller. This ensures teardown is best-effort and never blocks shutdown.

**Failure scenarios:**

| Condition | Behavior |
|---|---|
| Playwright not installed (`sync_playwright is None`) | `_ensure_ready()` returns string; `get_page()` raises `RuntimeError` with install instructions |
| `sync_playwright().start()` fails | `_ensure_ready()` returns `"Failed to start Playwright: …"`; propagates as `RuntimeError` |
| Browser launch fails (e.g., missing browser binary) | `_ensure_ready()` returns string with browser name and install hint; propagates as `RuntimeError` |
| Any `_page.close()` or `_context.close()` fails during `clear_context()` | Exception caught and silently discarded |
| Any `browser.close()` or `pw.stop()` fails during `close()` | Exception caught and silently discarded |
