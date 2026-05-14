# QA Agent — Architecture

## Overview

```
main.py  ──▶  app/graph.py (StateGraph)  ──▶  LLM + app/tools/  ──▶  infra/browser.py
                                                    │
                                                    └──▶ infra/storage.py
```

The agent has two modes: **graph** (automated capture + test) and **chat** (interactive investigation). Both share the same browser session and tool set.

## Graph Structure (automated flow)

```
                         ┌──────────────────────┐
                         │                      │
              ┌──────────┴──────────┐           │
              │     NAVIGATE        │           │
              │  (deterministic)    │           │
              └──────────┬──────────┘           │
                         │                      │
              ┌──────────┴──────────┐           │
              │      CAPTURE        │           │
              │  (deterministic)    │           │
              └──────────┬──────────┘           │
                         │                      │
              ┌──────────┴──────────┐           │
              │       AGENT         │           │
              │      (LLM)          │───────────┘
              └──────────┬──────────┘   (tool calls)
                         │
               (no tool calls)
                         │
              ┌──────────┴──────────┐
              │                     │
       set_reference           test mode
              │                     │
              ▼                     ▼
       ┌────────────┐        ┌──────────┐
       │SAVE_REFERENCE│      │ ANALYZE  │
       └──────┬─────┘      └────┬─────┘
              │                  │
             END          ┌──────┴─────┐
                          │   REPORT   │
                          └──────┬─────┘
                                END

Tools execution path:
    agent ──▶ tools ──▶ compact ──▶ agent   (compact_context called)
    agent ──▶ tools ──▶ agent               (any other tool called)
```

### Key structural change from v1

The old graph had `agent` as the entry point with `navigate` in its tool set. The LLM would call `navigate()` repeatedly (5+ times) instead of following the prompt's "navigate ONCE" instruction.

**Fix:** `navigate` and `capture` are now deterministic nodes that run before the LLM ever sees the conversation. The agent node's tool set (`_interaction_tools`) excludes `navigate`. The LLM can never trigger a navigation loop.

## Nodes

| Node | Type | What happens |
|---|---|---|
| `navigate` | Deterministic | Calls `BrowserManager.navigate(url)`, waits for `networkidle` |
| `capture` | Deterministic | Fetches HTML (100K cap) + full-page screenshot (compressed PNG), stores both in state |
| `agent` | LLM | Receives system prompt + page capture. Decides: login? scroll? compact? Returns tool calls or finishes |
| `tools` | Executor | Runs requested tools synchronously on main thread (Playwright's sync API is thread-bound) |
| `compact` | Deterministic | Strips all old messages except system prompt + compact summary + recent messages |
| `save_reference` | Deterministic | Extracts HTML + screenshot from tool results, persists to `data/<sha256>.json` |
| `analyze` | Deterministic + LLM | Runs `check_resources()` (deterministic) then `_llm_compare()` (vision LLM) |
| `report` | Deterministic | Writes `qa_report.csv` from collected issues |

## Routing

```python
def route_after_agent(state) -> str:
    if last_msg has tool_calls:
        return "tools"
    return "save_reference" if mode == "set_reference" else "analyze"

def route_after_tools(state) -> str:
    if last_tool was "compact_context":
        return "compact"
    return "agent"
```

## Two tool sets

| Context | Tools available | Includes navigate? |
|---|---|---|
| Graph agent (`_interaction_tools`) | click_link, fill_form, fetch_html, fetch_content, webpage_screenshot, scroll_down, scroll_to_top, compact_context, write_report, clear_session | No |
| Chat loop (`_tools`) | All 11 tools above + navigate | Yes |

The graph agent never sees `navigate` as a tool — it can't loop on it. The chat agent has `navigate` because users may say "go to this URL".

## State

```python
class AgentState(TypedDict):
    messages: list[BaseMessage]    # conversation history (auto-merged via add_messages)
    url: str                       # target URL
    mode: str                      # "set_reference" | "test"
    html: str                      # current page HTML (from capture or re-fetch)
    screenshot: str                # current page screenshot (base64 PNG data URI)
    issues: list[dict]             # collected QA issues
    report_path: str               # path to qa_report.csv
    credentials: dict               # from credential store
```

`html` and `screenshot` are populated by the `capture` node and updated by the `analyze` node. The `messages` key uses LangGraph's `add_messages` reducer — new messages are appended, not replaced.

## Chat Loop (main.py)

```
User input
  │
  ▼
Append HumanMessage
  │
  ▼
┌─────────────────────┐
│ For up to 12 rounds │
│                     │
│ auto_compact()  ─── checks token estimate, forces compaction at ~100K
│ chat_llm.invoke() ─ calls LLM with tools
│                     │
│ if error:           │
│   if 400/context:   │
│     compact harder  │
│     retry once      │
│   else:             │
│     report error    │
│                     │
│ if tool_calls:      │
│   execute tools     │
│   if compact_context│
│     inline compact  │
│     break round     │
│   else: continue    │
│ else:               │
│   break (done)      │
└─────────────────────┘
  │
  ▼
Print agent response
```

### Auto-compaction

```python
def _auto_compact(history, max_tokens=100_000):
    if estimate_tokens(history) < max_tokens:
        return history
    # Keep: system message + 1 most recent screenshot + last 6 messages
    # Replace middle with: "[Auto-compacted] Context was too large..."
```

### Error recovery

| Error | Response |
|---|---|
| 400 / context / token | Compact to 50K tokens, retry once |
| Any other error | Report to user, break current round |
| Empty response | Retry with plain LLM (no tools) |

## Tool Design

### Selector handling

`click_link` and `fill_form` support all Playwright-native selectors:

- **CSS:** `button`, `.class`, `#id`, `a[href="/login"]`, `input[name="email"]`
- **Text:** `text=Login`, `button:has-text("Sign In")`
- **ARIA:** `[aria-label="Close"]`

jQuery-only pseudo-classes (`:contains()`, `:visible`) are explicitly documented as unsupported.

`click_link` accepts an optional `text` parameter for convenience:

```python
click_link(selector="button", text="Login")
# internally becomes: button:has-text('Login')
```

### No hidden navigation

`fetch_html`, `fetch_content`, and `webpage_screenshot` take zero parameters. They always operate on the CURRENT page. There is no way to accidentally trigger a re-navigate by passing a URL. Navigation must be explicit: `navigate(url)` then `fetch_html()`.

### Context compaction

`compact_context(summary)` is a sentinel tool — it doesn't do the actual trimming itself. The graph's `compact_node` (or the chat loop's inline logic) detects the `ToolMessage` result and replaces the conversation with:

```
[SystemMessage]  (preserved)
[HumanMessage]   "[Context compacted] {summary}"
[AIMessage]      "Context compacted. Proceeding..."
[... recent messages after compact_context ...]
```

The summary is human-written by the agent and describes what it found and what it plans to do next.

## Browser Layer

`BrowserManager` is a module-level singleton in `infra/browser.py`:

```python
_browser_manager: Optional[BrowserManager] = None

def get_browser_manager() -> BrowserManager:
    global _browser_manager
    if _browser_manager is None:
        _browser_manager = BrowserManager()
    return _browser_manager
```

Key behaviors:
- Lazy initialization: browser, context, and page are created on first use
- Persistent session: cookies and localStorage survive across all tool calls
- All operations occur on one page — `get_page()` returns the same page every time
- `clear_context()` closes page + context (wipes cookies/storage), next `get_page()` creates fresh ones
- `navigate()` and `click()` wait for `networkidle` before returning
- `scroll_down()` waits for `networkidle` before scrolling (prevents scroll-on-unloaded-page)
- Screenshots are full-page (not viewport) and returned as base64 PNG data URIs
- `get_current_text()` strips `<script>`, `<style>`, `<nav>`, `<footer>`, `<header>`, `<aside>` before extracting text

## QA Checks

### Deterministic (`check_resources`)

Parses HTML with BeautifulSoup. For every `<a href>`, `<img src>`, `<link rel="stylesheet">`, and `<script src>`, makes a HEAD request (falls back to GET on 405). Reports any 400+ status or timeout as an issue.

Runs before (and independently of) the LLM comparison — catches link rot without consuming LLM tokens.

### Visual comparison (`_llm_compare`)

Sends the reference screenshot + current screenshot to the vision LLM with a prompt asking for structural/visual differences. Uses a plain LLM instance (no tool binding) to prevent hallucinated tool calls.

## Security

- **URL validation** (`_url.py`): blocks non-HTTP(S) schemes, localhost, loopback, private IPs, reserved IPs
- **No file system access** from within the browser — tools only interact through Playwright's API
- **Credentials** stored in `data/credentials.json`, passed to tools only when needed

## Configuration

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `openrouter` | `openai`, `openrouter`, or `local` |
| `OPENROUTER_API_KEY` | — | OpenRouter API key |
| `OPENROUTER_MODEL` | `openai/gpt-4o-mini` | Model (128K context) |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model (128K context) |
| `LOCAL_MODEL` | `gpt-4o-mini` | Model (128K context) |
| `LOCAL_BASE_URL` | `http://localhost:11434/v1` | Local server base URL |
| `LOCAL_API_KEY` | `not-needed` | Local server API key |
| `QA_VERBOSE` | `true` | Tool execution logging |
| `INCLUDE_HTML_IN_VLM` | `true` | HTML length in VLM prompt |
| `TOOL_CHOICE` | (none) | Force specific tool choice mode |
