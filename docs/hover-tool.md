# hover tool

Hovers the mouse cursor over an element on the current page.  Use this to
reveal hidden UI such as tooltips, dropdown menus, hover cards, or
expandable sections that only appear on mouse-over.

## Signature

```python
@tool
def hover(selector: str) -> str:
```

### Parameters

- **`selector`** (`str`): A Playwright CSS selector for the element to hover over.
  Supports standard CSS (`'button'`, `'.class'`, `'#id'`,
  `'[data-tooltip="help"]'`) and Playwright text selectors
  (`'text=Help'`, `'button:has-text("More")'`).  jQuery selectors like
  `:contains()` are **not** supported.

## Mechanics

Delegates to `BrowserManager.hover()`:

```python
from infra.browser import get_browser_manager

@tool
def hover(selector: str) -> str:
    mgr = get_browser_manager()
    mgr.hover(selector)
    page = mgr.get_page()
    return f"[hover] hovered '{selector}', still at {page.url} (title: {page.title()})"
```

`BrowserManager.hover()` (`infra/browser/_navigation.py:67-72`):

1. Calls Playwright's `page.hover(selector)` — this moves the virtual mouse
   to the element's center and fires the `mouseenter` / `mouseover` events.
2. Waits 500 ms for hover-triggered UI to appear (tooltips, dropdowns, etc.).
3. Returns the current page URL.

## Return format

- **Success**: `[hover] hovered '<selector>', still at <url> (title: <title>)`
- **Failure**: `[hover failed: <reason>]`

## When to use

Call `hover` when you need to:

- **Inspect a tooltip** — hover over an icon or link, then call
  `webpage_screenshot()` to see the tooltip text.
- **Open a dropdown menu** — hover over a nav item, then call
  `click_link` on a revealed menu item.
- **Test hover states** — verify that buttons change color on hover or
  that hidden controls appear.
- **Reveal delete/edit actions** — many tables hide row actions until
  you hover over the row.

The hover state is **not permanent** — moving the mouse elsewhere or
interacting with another element will dismiss hover-triggered UI.
Take a screenshot immediately after `hover()` to capture the state.

## Example workflow

```
> navigate to https://example.com/dashboard
> hover the user avatar icon
> take a screenshot and tell me if a dropdown menu appeared
```
