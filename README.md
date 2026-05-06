# QA Agent

A LangGraph agent that browses webpages, captures reference snapshots, and runs visual + deterministic QA checks — powered by a headless browser and a vision-capable LLM.

## Quick Start

```bash
pip install -r requirements.txt && playwright install chromium
cp .env.example .env   # add your API keys
python main.py --url https://example.com
```

The agent auto-detects whether a reference snapshot exists. If not, it captures one first. If one exists, it offers to test against it. After testing, a chat loop starts — ask questions, inspect pages, and the agent uses its browser tools to investigate.

## Modes

| Command | What it does |
|---|---|
| `python main.py --url <url>` | Interactive — auto-detects capture vs test |
| `python main.py --set-reference --url <url>` | Force capture a new reference snapshot |
| `python main.py --test --url <url>` | Run QA test against saved reference |

## How the Agent Loop Works

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

### Step by step

**1. Think** — The LLM receives a system prompt (describing the goal and available tools) plus the conversation history. It decides what to do next and emits either a tool call or a final answer.

**2. Act** — LangGraph's `ToolNode` executes whatever the LLM requested: navigate, scroll, take a screenshot, fetch HTML, click a link, fill a form, clear session, compact context, or write a report.

**3. Scan & scroll** — When the agent needs to locate an element on a long page, it takes a screenshot of the current viewport. If the target isn't visible, it calls `scroll_down(600)` and checks again. This repeats until the target is found or the page bottom is reached.

**4. Compact** — Once the target is found, the agent calls `compact_context(summary)` to flush all previous screenshots and HTML dumps from the context window. Only the system prompt and a human-readable summary remain. This keeps token usage low across an arbitrarily long browsing session.

**5. Repeat** — With a clean context, the agent clicks, fills forms, navigates, or continues scanning. The loop continues until the agent decides the task is complete.

## Project Layout

```
├── main.py              CLI entry point + interactive chat loop
├── app/
│   ├── graph.py         LangGraph StateGraph: 6 nodes, 2 conditional edges
│   ├── qa_utils.py      Deterministic checks (broken links, images, assets)
│   └── tools/           LangChain @tool functions (browser + utility tools)
├── infra/
│   ├── browser.py       Playwright headless browser (singleton, persistent session)
│   ├── config.py        LLM provider factory (OpenAI / OpenRouter)
│   ├── storage.py       Reference snapshot persistence (JSON on disk)
│   ├── credentials.py   Credential store (data/credentials.json)
│   └── validate.py      Startup environment checks
└── docs/                Architecture, tool references, test scenarios
```

## Tools

| Tool | Description |
|---|---|
| `navigate(url)` | Navigate browser to URL |
| `click_link(selector)` | Click a CSS selector |
| `fill_form(fields, submit)` | Fill form fields and optionally submit |
| `fetch_html(url)` | Get raw HTML |
| `fetch_content(url)` | Get visible text (no tags, no nav/footer) |
| `webpage_screenshot(url)` | Full-page PNG screenshot (base64) |
| `scroll_down(amount)` | Scroll down N pixels, returns position + at_bottom |
| `scroll_to_top()` | Scroll back to top |
| `clear_session()` | Wipe cookies/storage, close page (simulates logout) |
| `compact_context(summary)` | Trim old screenshots/HTML from context |
| `write_report(issues)` | Write CSV QA report from JSON issue array |

## Documents

- [Architecture](docs/ARCHITECTURE.md) — full component map, data flow, key design decisions
- [BrowserManager](docs/infra-browser.md) — how the persistent browser works
- [Test Scenarios](docs/scenarios.md) — 26 real QA scenarios for the target application
- [Adding New Tools](docs/adding-new-tools.md) — developer guide for extending the agent
- Tool references: [fetch_content](docs/fetch-content-tool.md), [screenshot](docs/screenshot-tool.md), [webpage_screenshot](docs/webpage-screenshot-tool.md)

## TODO

### Next up
- Login and signup flows
- Account balance / plan selection
- Hover interactions for CSS animations
- Click a link then compare with corresponding reference

### Discovery
- Track agent flow inside browser (visual replay)
- Detect and validate CSS animations
- Performance / load-time checks
- Browser console error capture

### Roadmap (Claude Suggestions)
1. **Test definition language** — Declarative YAML/JSON scenarios (navigate → fill → assert → screenshot)
2. **Assertion engine** — Deterministic text, attribute, existence, count, network, and console assertions
3. **Visual regression** — Pixel-level diffing; LLM only for classifying diffs, not detecting them
4. **Multi-scenario orchestration** — Parallel/sequential scenarios with per-scenario session isolation
5. **Structured reporting** — HTML reports with inline screenshots, JUnit XML for CI pipelines
6. **Test data management** — Fixture system with per-environment configs
7. **Browser robustness** — Wait strategies, iframe support, alerts, file upload, network interception
8. **Self-healing selectors** — Fallback strategies (text, aria labels, parent structure) when selectors break
9. **CI/CD integration** — Exit codes, env var overrides, artifact output
10. **Session & state management** — Multi-user scenarios, cookie/localStorage save/restore
