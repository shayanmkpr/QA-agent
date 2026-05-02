# webpage_screenshot tool

`webpage_screenshot` opens a URL in a headless browser and returns a full-page screenshot encoded as a base64 PNG data URI.

## Context

- **Upstream caller**: LangGraph `ToolNode` (`app/graph.py`) invokes this when the LLM emits a `tool_call` named `webpage_screenshot`.
- **Downstream dependency**: `infra.browser.BrowserManager.screenshot(url)`.
- **Runtime environment**: Same process as the agent graph. Requires Playwright and Chromium.

## Mechanics

The tool delegates to the browser manager's screenshot helper:

```python
from langchain_core.tools import tool
from infra.browser import get_browser_manager

@tool
def webpage_screenshot(url: str) -> str:
    """Open a URL in a headless browser and return a full-page screenshot as a base64-encoded PNG data URI.

    Use this when you need a complete screenshot of a specific webpage.
    The returned format matches the screen screenshot tool (data:image/png;base64,...)
    so it can be consumed by vision-capable models the same way.
    """
    return get_browser_manager().screenshot(url)
```

`BrowserManager.screenshot` performs:

1. Ensures the browser is started via `_ensure_ready()`.
2. Creates a new page, navigates to `url`, and waits for `networkidle`.
3. Captures a full-page PNG (`page.screenshot(full_page=True)`).
4. Base64-encodes the bytes and returns a string prefixed with `data:image/png;base64,`.

## Error handling

If Playwright is missing, startup fails, or navigation throws, `_ensure_ready()` or the page interaction returns an error string wrapped in `[webpage_screenshot failed: ...]`. This string is passed back as the tool result, keeping the graph stable.

## Return format

- **Success**: `data:image/png;base64,<base64-encoded-png-bytes>`
- **Failure**: A single string describing the error

## Distinction from screen screenshot

- `screenshot` (`app/tools/screenshot.py`) captures the user's local desktop via `PIL.ImageGrab`.
- `webpage_screenshot` captures a remote webpage via Playwright.

Both return the same `data:image/png;base64,...` format, so vision-capable models consume them identically.
