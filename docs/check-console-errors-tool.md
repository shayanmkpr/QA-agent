# check_console_errors tool

Reads and clears the browser's console log, reporting JavaScript errors
(`console.error()`) and warnings (`console.warn()`) that have accumulated
since the last call (or since the page was first loaded).

## Signature

```python
@tool
def check_console_errors() -> str:
```

No parameters.  Always operates on the logs collected in the current browser
session.  Does NOT navigate — the page must already be loaded.

## Mechanics

Console monitoring is set up automatically when the Playwright page is first
created (`BrowserManager.get_page()` → `_setup_monitoring` in
`infra/browser/_monitoring.py`).  A `console` event listener captures every
`console.error()` and `console.warn()` call (message text + file:line location).

Calling the tool:

```python
from infra.browser import get_browser_manager

@tool
def check_console_errors() -> str:
    return get_browser_manager().get_console_summary()
```

`get_console_summary()` in `infra/browser/_monitoring.py`:

1. Separates errors from warnings.
2. Formats a human-readable summary (errors first, then up to 50 warnings —
   the remainder shows a count).
3. Clears the internal list so subsequent checks only return new entries.

The log is also cleared when `BrowserManager.clear_context()` is called
(e.g. during `clear_session()` or the scenario runner's auth re-login).

## Return format

- **No issues**: `"No console errors or warnings found."`
- **With issues**: Multi-line string:
  ```
  Console — 3 error(s), 12 warning(s)

  Errors:
    • TypeError: Cannot read property 'x' of undefined  (app.js:45)
    • Failed to load resource: 404  (favicon.ico)
    • Uncaught Error: API timeout  (api.js:128)

  Warnings:
    • React state update on unmounted component  (react-dom.js:200)
    • …
    … and 2 more warnings
  ```
- **Failure**: `[check_console_errors failed: <reason>]`

## When to use

Call after clicking a button, submitting a form, or navigating to a new page
to verify that no unexpected JavaScript errors occurred.  Common use cases:

- **SPA route changes** — client-side navigation may silently throw errors.
- **Form validation** — broken validation logic often logs to console.
- **Third-party scripts** — analytics, chat widgets, or ads may fail and log errors.
- **Lazy-loaded content** — dynamically imported modules or images that fail.

Pair with `check_network()` to cover both frontend (JS) and backend (HTTP)
surface-level QA in a single pass.
