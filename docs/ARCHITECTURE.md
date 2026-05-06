# QA Agent — Architecture

A LangGraph agent that browses webpages with a headless Playwright browser, captures reference snapshots, and runs visual + deterministic QA checks via a vision-capable LLM.

```
main.py  ──▶  app/graph.py (StateGraph)  ──▶  LLM + app/tools/  ──▶  infra/storage.py
```

## Component Map

| Component | Role |
|---|---|
| `main.py` | CLI entry point, argument parsing, interactive post-test chat loop |
| `app/graph.py` | LangGraph `StateGraph` with 6 nodes, 2 conditional routing functions |
| `app/tools/` | LangChain `@tool` functions bound to the LLM (browser + utility tools) |
| `app/qa_utils.py` | Deterministic resource checks (broken links, images, stylesheets, scripts) |
| `infra/browser.py` | Playwright headless Chromium singleton — persistent session across tool calls |
| `infra/config.py` | LLM provider factory (OpenAI / OpenRouter) |
| `infra/storage.py` | Reference snapshot persistence (JSON on disk, keyed by URL hash) |
| `infra/credentials.py` | Credential store (`data/credentials.json`) |
| `infra/validate.py` | Startup environment validation (API keys, data dir, Playwright availability) |

## Agent Loop

```
                     ┌──────────────────────┐
                     │                      │
                     ▼                      │
              ┌───────────┐                 │
              │   AGENT   │                 │
              │  (think)  │                 │
              └─────┬─────┘                 │
                    │                       │
                    │ LLM outputs           │
                    │ tool_calls?           │
                    │                       │
            ┌───────┴───────┐               │
            │               │               │
           YES              NO              │
            │               │               │
            ▼               ▼               │
     ┌──────────┐   ┌──────────────┐        │
     │  TOOLS   │   │ save_ref /   │        │
     │  (act)   │   │ analyze /    │──▶ END │
     └────┬─────┘   │ END          │        │
          │         └──────────────┘        │
          │                                 │
          │ last tool was                   │
          │ compact_context?                │
          │                                 │
    ┌─────┴─────┐                           │
    │           │                           │
   YES         NO                           │
    │           │                           │
    ▼           └───────────────────────────┘
 ┌──────────┐
 │ COMPACT  │
 │ (trim)   │──▶ AGENT
 └──────────┘
```

### Nodes

| Node | What happens |
|---|---|
| **agent** | Invokes the LLM with system prompt + full message history. The LLM generates text and/or tool calls. |
| **tools** | LangGraph's `ToolNode` executes requested tool calls (navigate, click, scroll, screenshot, etc.). Results are appended as `ToolMessage`s. |
| **compact** | Trims the conversation: removes all old screenshots and verbose HTML outputs. Keeps only the system message + the agent's summary from `compact_context()`. |
| **save_reference** | Extracts the final HTML + screenshot from tool results, persists them to disk via `storage.save_reference()`. |
| **analyze** | Runs `check_resources()` (deterministic) on current HTML, loads the reference snapshot, and calls `_llm_compare()` (vision-based comparison) if a reference exists. |
| **report** | Writes all collected issues to `qa_report.csv`. |

### Routing

- **`route_after_agent`** — If the LLM response contains `tool_calls`, go to `tools`. Otherwise, route to `save_reference` (set-reference mode), `analyze` (test mode), or `END`.
- **`route_after_tools`** — If the most recent tool call was `compact_context`, go to `compact` node. Otherwise, loop back to `agent`.

## The Scan → Compact → Act Pattern

The core innovation is context compaction between scanning and acting:

1. **Scan** — The agent takes a `webpage_screenshot()` of the current viewport and/or calls `fetch_content()` to read visible text.
2. **Check** — If the target element (link, button, form) isn't in view, the agent calls `scroll_down(600)` and repeats step 1. It continues until the target is found or `at_bottom` is `true`.
3. **Compact** — Once found, the agent calls `compact_context(summary)` with a description of what it found and what it plans to do next. The `compact` node strips all previous screenshots, HTML dumps, and scroll results from the message history.
4. **Act** — With a clean, small context, the agent clicks, fills forms, or performs whatever action is needed.

This means the agent can scan arbitrarily long pages without accumulating context-killing amounts of token data. Each scan round adds a screenshot + HTML, and the compaction step removes them immediately after the target is identified.

## Modes

### `set_reference`
Captures a baseline snapshot. The agent navigates to the URL, logs in (if credentials are available and auth is detected), fetches HTML, takes a full-page screenshot, and saves both to `data/<url-hash>.json`.

### `test`
Runs comparison against the saved reference. Same navigation + login flow, then:

1. **Deterministic checks** — `check_resources()` parses HTML with BeautifulSoup, runs HEAD/GET requests on every `<a href>`, `<img src>`, `<link rel="stylesheet">`, and `<script src>`. Reports any HTTP 400+ or timeout as an issue.

2. **LLM visual comparison** — `_llm_compare()` sends the reference screenshot + current screenshot to the vision-capable LLM. The LLM returns a JSON array of structural/visual issues (layout shifts, missing elements, content changes, color/font diffs). HTML length comparison is optionally included to help detect structural changes.

### Routing flow

```
agent ──▶ tools ──▶ agent  (loop while tool calls remain)
agent ──▶ save_reference ──▶ END  (set_reference done)
agent ──▶ analyze ──▶ report ──▶ END  (test done)
tools ──▶ compact ──▶ agent  (context compaction)
```

## Key Design Decisions

- **Vision comparison uses `llm_plain`** — A separate LLM instance without tool binding prevents hallucinated tool calls during comparison.
- **SSRF mitigation** — The `_validate_url()` helper blocks non-HTTP(S) schemes, localhost, loopback addresses, and private IP ranges in all network-fetching tools.
- **Deterministic first, LLM second** — `check_resources()` runs before (and independently of) `_llm_compare()`, catching broken links without consuming LLM tokens.
- **Storage is abstracted** — `storage.py` is the sole boundary for snapshot persistence. Swapping JSON-on-disk for a database only touches that file.
- **Singleton browser** — `BrowserManager` is a module-level singleton. All tools share the same browser, context, and page, so cookies and localStorage survive across tool calls.
- **Context compaction** — The `compact_context` tool + `compact` node pattern keeps the conversation history small by stripping intermediate screenshots and HTML dumps after each successful scan. Without this, every scroll + screenshot round would consume thousands of tokens and rapidly exhaust the context window.

## Configuration

Set in `.env` (copy from `.env.example`):

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `openrouter` | `openai` or `openrouter` |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model for OpenAI provider |
| `OPENROUTER_API_KEY` | — | OpenRouter API key |
| `OPENROUTER_MODEL` | `openai/gpt-4o-mini` | Model for OpenRouter provider |
| `TOOL_CHOICE` | (none) | Force specific tool choice mode |
| `INCLUDE_HTML_IN_VLM` | `true` | Include HTML length in VLM comparison prompt |

Add new LLM providers by extending the factory function in `infra/config.py`.

## Tools Available to the LLM

### Browser tools
| Tool | Returns |
|---|---|
| `navigate(url)` | Current URL + page title |
| `click_link(selector)` | URL + title after navigation |
| `fill_form(fields, submit_selector)` | URL + title after submission |
| `fetch_html(url="")` | Raw HTML (truncated at 100K chars) |
| `fetch_content(url="")` | Visible text, no tags, no nav/footer/header |
| `webpage_screenshot(url="")` | Full-page base64 PNG data URI |
| `scroll_down(amount=600)` | JSON: `{scroll_y, scrolled, at_bottom}` |
| `scroll_to_top()` | JSON: `{scroll_y: 0}` |
| `clear_session()` | Wipes cookies/storage, closes page |

### Utility tools
| Tool | Returns |
|---|---|
| `compact_context(summary)` | Signal + preserved summary |
| `write_report(issues)` | CSV written to disk |
