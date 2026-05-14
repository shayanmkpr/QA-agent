# QA Agent

A production-ready AI agent that browses websites, captures reference snapshots, and runs visual + deterministic QA checks using a headless browser and a vision-capable LLM.

## Quick Start

```bash
pip install -r requirements.txt && playwright install chromium
cp .env.example .env   # add your API keys
python main.py --url https://example.com
```

The agent auto-detects whether a reference snapshot exists. If not, it captures one. If yes, it offers to test against it. After testing, an interactive chat loop starts — ask questions, inspect pages, click things, fill forms, and the agent uses its browser to investigate.

## Modes

| Command | What it does |
|---|---|
| `python main.py --url <url>` | Interactive — auto-detects capture vs test |
| `python main.py --set-reference --url <url>` | Force capture a new reference snapshot |
| `python main.py --test --url <url>` | Run QA test against saved reference |

### Scenario Mode (NEW)

Run all QA scenarios from a markdown file. The agent parses the scenarios, executes each one using the LLM + browser, and writes a per-scenario pass/fail report.

```bash
python main.py --scenarios --url https://app.example.com
python main.py --scenarios --scenarios-file custom_scenarios.md --url https://app.example.com
```

**How it works:**
1. Parses `docs/scenarios.md` into structured scenarios (26 by default)
2. Manages auth state — clears session for auth-testing scenarios, logs in for feature scenarios
3. Runs each scenario through an LLM agent loop (up to 25 rounds each)
4. The LLM follows steps, interacts with the page, and issues a verdict: `VERDICT: PASS` or `VERDICT: FAIL`
5. Writes results to `qa_scenarios_report.csv`

**Report columns:** Scenario ID, Section, Title, Status, Duration (s), Steps, Findings, Error

| Status | Meaning |
|---|---|
| `PASS` | All expected outcomes met |
| `FAIL` | One or more expected outcomes not met |
| `ERROR` | Scenario could not be executed (LLM error, login failure, timeout) |
| `SKIP` | Scenario was skipped |

**Scenarios file format** (`docs/scenarios.md`):
```markdown
## 1. Section Name

### Scenario 1: Title

- Step one
- Step two

**Expected:**
- Expected outcome one
- Expected outcome two
```

Scenarios 3-5 are treated as auth scenarios (start with clean session). Scenarios 6+ require login (auto login setup before execution).

## How It Works

### Graph flow (automated test)

```
navigate ──▶ capture ──▶ agent ──▶ tools ──▶ agent ──▶ analyze ──▶ report
  (auto)      (auto)     (LLM)     (exec)    (LLM)    (checks)    (CSV)
                              \______________/
                              loop: click, fill,
                              scroll, re-capture
```

1. **navigate** — Deterministic: opens the URL in Playwright. No LLM involved.
2. **capture** — Deterministic: fetches full HTML (capped at 100K chars) and takes a full-page screenshot. No LLM involved.
3. **agent** — LLM receives the HTML + screenshot. Decides: is login needed? Any interactions? The agent does NOT have a `navigate` tool, so it can never loop on navigation.
4. **tools** — Executes whatever the LLM requested (click, fill form, scroll, re-capture, compact, etc.). Results feed back to the agent.
5. **compact** — When the agent calls `compact_context(summary)`, old screenshots and HTML are stripped from context — only the summary and recent messages remain. This keeps the context window small across many interactions.
6. **analyze** — Runs deterministic checks (broken links, images, scripts, stylesheets) + LLM-powered visual comparison against the reference snapshot.
7. **report** — Writes all issues to `qa_report.csv`.

### Chat flow (interactive)

After the test, a chat loop starts. You type commands in natural language. The agent has all browser tools including `navigate` (for when you say "go to X"). It also has:

- **Auto-compaction**: monitors context token count. When approaching ~100K tokens, it force-compacts to prevent API errors.
- **Error recovery**: if the LLM call fails (e.g. context overflow), it auto-compacts harder and retries.

### The Scan → Compact → Act pattern

1. **Scan** — `webpage_screenshot()` or `fetch_content()` to see the current viewport.
2. **Scroll if needed** — `scroll_down(600)` and re-scan until the target is found or `at_bottom` is true.
3. **Compact** — `compact_context("Found login button in header. Next: click it.")` — strips all previous screenshots and HTML from context.
4. **Act** — Click, fill, or interact with the target.

This pattern means the agent can browse arbitrarily long pages without exhausting the context window.

## Tools

| Tool | Signature | Description |
|---|---|---|
| `navigate` | `(url: str)` | Navigate browser to a URL (chat mode only) |
| `click_link` | `(selector: str, text: str = "")` | Click an element. Supports CSS, `text=`, `:has-text()`. Optional `text` param matches by visible text. |
| `fill_form` | `(fields: str, submit_selector: str = "")` | Fill form fields (JSON mapping selectors → values) and optionally submit |
| `fetch_html` | `()` | Get raw HTML of current page (capped at 100K chars) |
| `fetch_content` | `()` | Get visible text of current page (scripts/styles/nav stripped) |
| `webpage_screenshot` | `()` | Full-page PNG screenshot of current page (base64, compressed) |
| `scroll_down` | `(amount: int = 600)` | Scroll down, returns `{scroll_y, scrolled, at_bottom}` |
| `scroll_to_top` | `()` | Scroll back to top of page |
| `clear_session` | `()` | Wipe cookies/storage, close page (simulates logout) |
| `compact_context` | `(summary: str)` | Trim old screenshots/HTML from context, keep only summary |
| `write_report` | `(issues: str)` | Write CSV QA report from JSON issue array |

### Selector guide

Valid Playwright selectors for `click_link` and `fill_form`:

| Type | Example |
|---|---|
| CSS tag | `button`, `a`, `input` |
| CSS class | `.btn-primary`, `.nav-link` |
| CSS ID | `#login-button` |
| CSS attribute | `a[href="/login"]`, `input[name="email"]` |
| Text match | `text=Login`, `text=Sign In` |
| Has text | `button:has-text("Get Started")` |
| ARIA | `[aria-label="Close"]` |

**Do NOT use jQuery selectors** — `:contains()`, `:visible`, `:hidden` are NOT supported.

## Project Layout

```
main.py                 CLI entry point + interactive chat loop
app/
├── graph.py            LangGraph StateGraph: 8 nodes, 2 conditional edges
├── qa_utils.py         Deterministic checks (broken links, images, assets, scripts)
└── tools/              LangChain @tool functions
    ├── navigate.py     Browser navigation
    ├── click_link.py   Click elements (CSS + text-based)
    ├── fill_form.py    Fill and submit forms
    ├── fetch_html.py   Get raw HTML
    ├── fetch_content.py Get visible text
    ├── webpage_screenshot.py Full-page screenshot
    ├── scroll.py       Scroll down / scroll to top
    ├── screenshot.py   Desktop screenshot (PIL ImageGrab)
    ├── compact_context.py Context compaction signal
    ├── write_report.py Write CSV report
    ├── clear_session.py Clear browser session
    └── _url.py         URL validation (SSRF protection)
infra/
├── browser.py          Playwright headless Chromium singleton
├── config.py           LLM provider factory (OpenAI / OpenRouter)
├── storage.py          Reference snapshot persistence (JSON on disk)
├── credentials.py      Credential store (data/credentials.json)
├── validate.py         Startup environment checks
└── logging.py          Verbose logging (QA_VERBOSE env var)
```

## Configuration

Set in `.env`:

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `openrouter` | `openai`, `openrouter`, or `local` |
| `OPENROUTER_API_KEY` | — | OpenRouter API key |
| `OPENROUTER_MODEL` | `openai/gpt-4o-mini` | Model (OpenRouter) |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model (OpenAI) |
| `LOCAL_MODEL` | `gpt-4o-mini` | Model (local) |
| `LOCAL_BASE_URL` | `http://localhost:11434/v1` | Local server base URL |
| `LOCAL_API_KEY` | `not-needed` | Local server API key |
| `QA_VERBOSE` | `true` | Set to `false` to silence tool logs |
| `INCLUDE_HTML_IN_VLM` | `true` | Include HTML length in visual comparison |
