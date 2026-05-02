# QA Agent

A LangGraph agent that fetches the HTML of a given URL.

## Project layout

```
qa-agent/
├── infra/
│   └── config.py    # LLM providers — switch with LLM_PROVIDER env var
├── app/
│   ├── tools.py     # fetch_html tool
│   └── graph.py     # LangGraph agent loop
├── main.py          # CLI entry point
└── requirements.txt
```

**`infra/`** — infrastructure (models, keys, providers).  
**`app/`** — agent logic (tools, graph). The app never imports model-specific code directly.

## How it works

```
User gives URL
       │
       ▼
┌─────────────┐     tool_call?     ┌───────────┐
│   agent     │ ─────────────────▶ │  tools    │
│  (LLM)      │ ◀──────────────── │ (fetch)   │
└─────────────┘   tool result      └───────────┘
       │
       │ no tool call (done)
       ▼
   HTML output
```

1. **Graph starts** at the `agent` node with the URL in state.
2. The LLM sees the user message and emits a **tool call** for `fetch_html(url)`.
3. The `route` function detects the tool call and sends execution to the `tools` node.
4. `tools` runs `requests.get(url)` and returns the raw HTML as a tool result.
5. Control loops back to `agent` — the LLM now has the HTML in its context and returns it as the final response.
6. The `html` field in state is set from the LLM's final message, and the graph ends.

## Setup

```bash
pip install -r requirements.txt
```

## Providers

Set `LLM_PROVIDER` in `.env` (defaults to `openrouter`).

### OpenAI

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini    # optional, default shown
```

### OpenRouter

```env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=openai/gpt-4o-mini   # optional, default shown
```

To add a new provider (e.g. Anthropic): add a factory function in `infra/config.py` and register it in `_registry`. Nothing else changes.

## Adding a new tool/feature

1. **Define the tool** in `app/tools.py` using the `@tool` decorator:
   ```python
   @tool
   def screenshot() -> str:
       """Take a screenshot of the current screen."""
       ...
       return base64_image
   ```
   The docstring is the tool description the LLM sees — make it descriptive.

2. **Import and register** it in `app/graph.py`:
   ```python
   from app.tools import fetch_html, screenshot   # ← import
   tools = [fetch_html, screenshot]               # ← add to list
   ```
   That's it. The LLM auto-discovers tools via `.bind_tools(tools)`.

3. **If the tool needs new state** (e.g. an image URL), extend `AgentState` in `graph.py`.

4. **If the tool needs new dependencies**, add them to `requirements.txt`.

## Run

```bash
python main.py
# URL: https://example.com
```
