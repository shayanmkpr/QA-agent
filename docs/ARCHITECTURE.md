# QA Tester Agent — Architecture

LangGraph agent capturing web page snapshots and running visual/structural QA tests via a vision-capable LLM, plus deterministic resource checks (links, images, stylesheets, scripts).

`main.py` → `app/graph.py` (StateGraph) → LLM + `app/tools/` → `infra/storage.py`

## Components

`main.py` — CLI entry point, interactive flow, post-test chat loop  
`app/graph.py` — StateGraph: nodes (agent, tools, save_reference, analyze, report) and routing  
`app/tools/` — LangChain `@tool` functions bound to the LLM  
`app/qa_utils.py` — Deterministic checks (broken links, images, assets)  
`infra/config.py` — LLM provider factory (OpenAI / OpenRouter)  
`infra/browser.py` — Playwright headless Chromium manager  
`infra/storage.py` — JSON snapshot persistence in `data/`  
`infra/validate.py` — Startup validation (API keys, data dir, Playwright)

## Flow

Two modes, selected by `AgentState.mode`:

**set_reference** — LLM emits `fetch_html(url)` + `webpage_screenshot(url)`, executed via Playwright. Routes to `save_reference_node`, writing HTML + base64 screenshot JSON to `data/<url-hash>.json`.

**test** — Same tool loop fetches current HTML + screenshot. Routes to `analyze_node`, runs `check_resources()` on current HTML, loads reference snapshot, and calls `_llm_compare()` — a plain (non-tool-bound) LLM invocation comparing screenshots via vision. Returns JSON issue array. Routes to `report_node`, writing `qa_report.csv`. Back in `main.py`, user enters a chat loop with a fresh LLM instance for follow-up.

**Routing** — `agent → tools` (loop while tool calls), `agent → save_reference` (set_reference done), `agent → analyze` (test done), `tools → agent`, `save_reference/report → END`.

## Key Decisions

- **Vision comparison** uses `llm_plain` (no tools) to avoid hallucinated tool calls.
- **URL validation** blocks non-HTTP(S), localhost, loopback, and private IPs — SSRF mitigation.
- **Deterministic checks** run before LLM comparison, catching broken links without LLM cost.
- **Storage** is JSON-on-disk; `storage.py` is the sole abstraction boundary — swap to DB without touching app/ logic.

## Configuration

Set in `.env` (see `.env.example`): `LLM_PROVIDER` (openai/openrouter), `OPENAI_API_KEY`, `OPENAI_MODEL` (default `gpt-4o-mini`), `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` (default `openai/gpt-4o-mini`). Add providers via factory in `infra/config.py`.

## Setup & Usage

```bash
pip install -r requirements.txt && playwright install chromium
cp .env.example .env   # edit API key
python main.py                              # interactive, auto-detects reference
python main.py --set-reference --url <url>  # force capture
python main.py --test --url <url>           # test against reference
```

After test, chat loop starts. Type questions to investigate with browser tools, or `done` to exit.

## Tools Available to LLM

`fetch_html(url)` — Raw HTML via Playwright  
`fetch_content(url)` — Visible text (no tags) via Playwright + BeautifulSoup  
`webpage_screenshot(url)` — Full-page base64 screenshot via Playwright  
`screenshot()` — Screen capture of user's display via Pillow
