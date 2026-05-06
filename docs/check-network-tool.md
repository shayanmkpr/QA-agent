# check_network tool

Reads and clears the browser's network activity log, reporting failed requests,
HTTP error responses (4xx / 5xx), and slow requests (> 3 seconds) that have
accumulated since the last call (or since the page was first loaded).

## Signature

```python
@tool
def check_network() -> str:
```

No parameters.  Always operates on the logs collected in the current browser
session.  Does NOT navigate — the page must already be loaded.

## Mechanics

Network monitoring is set up automatically when the Playwright page is first
created (`BrowserManager.get_page()` → `_setup_monitoring` in
`infra/browser/_monitoring.py`).  Three Playwright event listeners are attached:

| Event | Tracked | Entry kind |
|---|---|---|
| `requestfailed` | Connection errors, DNS failures, timeouts | `failed` |
| `response` | HTTP 4xx / 5xx status codes | `error_response` |
| `response` | Any response taking > 3 seconds (regardless of status) | `slow` |

Request → response duration is measured by recording `time.time()` on the
`request` event and computing the delta on the matching `response` event
(matched via `id(request)`).

Calling the tool:

```python
from infra.browser import get_browser_manager

@tool
def check_network() -> str:
    return get_browser_manager().get_network_summary()
```

`get_network_summary()` in `infra/browser/_monitoring.py`:

1. Partitions entries by kind.
2. Formats a human-readable summary with counts and details.
3. Clears the internal list so subsequent checks only return new entries.

The log is also cleared when `BrowserManager.clear_context()` is called
(e.g. during `clear_session()` or the scenario runner's auth re-login).

## Return format

- **No issues**: `"No network issues found."`
- **With issues**: Multi-line string:
  ```
  Network — 1 failed, 3 error response(s), 1 slow request(s)

  Failed requests:
    • https://example.com/broken.js  (net::ERR_CONNECTION_REFUSED)

  Error responses (4xx / 5xx):
    • https://example.com/api/foo  → 500  (0.82s)
    • https://example.com/api/bar  → 404

  Slow requests (> 3 s):
    • https://example.com/api/large  → 200  (5.23s)
  ```
- **Failure**: `[check_network failed: <reason>]`

## When to use

Call after navigating to a page or after a form submission to catch:
- **Broken asset URLs** (JS, CSS, images 404)
- **Failing API calls** (4xx auth errors, 5xx server errors)
- **Slow endpoints** that degrade the user experience

Pair with `check_console_errors()` for a complete surface-level QA check.
