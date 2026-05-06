# fetch_content tool

Fetches the visible, human-readable text of the **current** browser page (HTML tags removed, nav/footer/header/aside stripped).

## Signature

```python
@tool
def fetch_content() -> str:
```

No parameters. Always operates on the page currently loaded in the browser. Does NOT navigate — call `navigate(url)` first if you need to go to a URL.

## Mechanics

Delegates to `BrowserManager.get_current_text()`:

```python
from infra.browser import get_browser_manager

@tool
def fetch_content() -> str:
    return get_browser_manager().get_current_text()
```

`get_current_text()` fetches the full HTML via `page.content()`, then uses BeautifulSoup to strip `<script>`, `<style>`, `<nav>`, `<footer>`, `<header>`, and `<aside>` elements. Returns deduplicated non-empty text lines.

## Return format

- **Success**: Multi-line string with visible page text.
- **Failure**: `[fetch_content failed: <reason>]`.

## When to use

Choose `fetch_content` over `fetch_html` when you need the **semantic content** of the page (article text, button labels, product descriptions) rather than raw markup for selector hunting or debugging.
