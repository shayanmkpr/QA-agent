# webpage_screenshot tool

Takes a full-page screenshot of the **current** browser page and returns it as a compressed base64 PNG data URI.

## Signature

```python
@tool
def webpage_screenshot() -> str:
```

No parameters. Always screenshots the page currently loaded in the browser. Does NOT navigate — call `navigate(url)` first if you need to go to a URL.

## Mechanics

Delegates to `BrowserManager.screenshot_current()` then passes the result through `compress_image()`:

```python
from infra.browser import get_browser_manager
from app.qa_utils import compress_image

@tool
def webpage_screenshot() -> str:
    result = get_browser_manager().screenshot_current()
    if result.startswith("data:image"):
        result = compress_image(result)
    return result
```

`screenshot_current()` takes a `full_page=True` PNG screenshot and encodes it as a base64 data URI. `compress_image()` resizes it so the longest edge is ≤1024px (reducing ~2-3MB base64 to ~120KB).

## Return format

- **Success**: `data:image/png;base64,<compressed-png-bytes>`
- **Failure**: `[webpage_screenshot failed: <reason>]`

## Distinction from desktop screenshot

- `screenshot` (`app/tools/screenshot.py`) captures the user's **local desktop** via `PIL.ImageGrab`.
- `webpage_screenshot` captures the **browser page** via Playwright.

Both return the same `data:image/png;base64,...` format.
