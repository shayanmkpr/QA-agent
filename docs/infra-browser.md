# BrowserManager

`BrowserManager` lazily initializes a headless Playwright browser (default Chromium) and exposes page-interaction helpers used by the agent's web tools.

## Context

- **Upstream callers**: `app/tools/fetch_html.py`, `app/tools/fetch_content.py`, and `app/tools/webpage_screenshot.py` all call `get_browser_manager()` to obtain a global singleton instance.
- **Downstream dependencies**: `playwright.sync_api.sync_playwright`, `BeautifulSoup` (for text extraction).
- **Runtime environment**: The same Python process as the agent graph. Requires `playwright` + Chromium binaries installed.

## Lifecycle

Initialization is deferred until the first `_ensure_ready()` call.

1. `sync_playwright()` is evaluated on import. If missing, `sync_playwright` is set to `None` and all subsequent calls return an error string.
2. On first use, `_ensure_ready()` starts Playwright (`sync_playwright().start()`), then launches Chromium (`self._browser = self._pw.chromium.launch()`).
3. The manager creates a fresh `page` per operation (`new_page()`) and closes it in a `finally` block.

Cleanup is explicit:

- `close()` shuts down the browser and stops the Playwright driver.
- Context-manager support (`__enter__` / `__exit__`) guarantees cleanup even if the calling code raises.

## Surface area

| Method | Input | Output | Side effects |
|---|---|---|---|
| `get_html(url)` | URL string | Raw HTML string or error message | Launches browser if not ready; creates and destroys a page. |
| `get_text(url)` | URL string | Visible text (no tags, no scripts) | Calls `get_html`, then parses with BeautifulSoup. |
| `screenshot(url)` | URL string | `data:image/png;base64,<...>` URI or error message | Launches browser if not ready; creates and destroys a page. |
| `close()` | None | None | Closes browser and driver if open. |

## Error handling

`_ensure_ready()` returns an error string (never raises) for three failure modes:

1. **Playwright not installed** -> `"Playwright is not installed. Please run: pip install playwright && playwright install chromium"`
2. **Playwright startup failure** -> `"Failed to start Playwright: <exc>"`
3. **Browser launch failure** -> formatted string with the browser type, exception, and installation hint.

Public methods (`get_html`, `screenshot`) check for this error string and return it wrapped in a `[... failed: ...]` prefix instead of propagating an exception. This prevents the LangGraph `ToolNode` from crashing the graph when the browser is unavailable.

## Text extraction (`get_text`)

After fetching HTML, `get_text` uses BeautifulSoup to:

1. Remove `<script>`, `<style>`, `<nav>`, `<footer>`, `<header>`, and `<aside>` elements.
2. Extract visible text with `soup.get_text(separator="\n")`.
3. Strip each line and drop empty lines.

The result is plain prose suitable for LLM consumption without markup noise.

## Singleton

`get_browser_manager()` holds a module-level `_browser_manager` reference. The first call constructs `BrowserManager()`; subsequent calls return the same instance. This avoids repeated Playwright startup cost across multiple tool calls in a single agent loop.
