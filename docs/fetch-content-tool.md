# fetch_content tool

`fetch_content` fetches a URL through the headless browser and returns the page's visible, human-readable text content with HTML tags removed.

## Context

- **Upstream caller**: LangGraph `ToolNode` (`app/graph.py`) invokes this when the LLM emits a `tool_call` named `fetch_content`.
- **Downstream dependency**: `infra.browser.BrowserManager.get_text(url)`.
- **Runtime environment**: Same process as the agent graph. Requires Playwright and Chromium.

## Mechanics

The tool is a thin LangChain `@tool` wrapper around `get_browser_manager().get_text(url)`:

```python
from langchain_core.tools import tool
from infra.browser import get_browser_manager

@tool
def fetch_content(url: str) -> str:
    """Fetch a URL and return its extracted readable text content (no HTML tags).

    Use this when you want to read the actual page content, not raw markup.
    """
    return get_browser_manager().get_text(url)
```

When called, `BrowserManager` performs the following:

1. Ensures the headless Chromium browser is started.
2. Opens a new page, navigates to `url`, and waits until the network is idle.
3. Retrieves the raw HTML.
4. Passes the HTML through BeautifulSoup to strip scripts, styles, navigation, headers, footers, and asides.
5. Returns clean text with empty lines removed.

## Error handling

If the browser is unavailable or navigation fails, `get_text` returns an error string starting with `[get_html failed:` or `[webpage_screenshot failed:`. This string becomes the `content` of the `ToolMessage` returned to the LLM, preventing graph crashes.

## Return format

- **Success**: A single multi-line string containing visible page text.
- **Failure**: A single string containing the failure reason.

## When to use

The LLM should choose `fetch_content` over `fetch_html` when it needs the semantic content of a page (e.g., article body, product description) rather than raw markup for parsing or debugging.
