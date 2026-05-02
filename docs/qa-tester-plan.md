# QA Tester Agent — Implementation Plan

## Goal
Transform the existing URL fetcher agent into a QA tester that:
1. Captures a reference snapshot of a webpage (raw HTML + screenshot).
2. Compares a live page against that reference to find abnormalities.
3. Writes a structured CSV report with findings categorized as `frontend`, `backend`, or `both`.

## Architecture Overview

```
Entry → agent (fetches page via existing tools)
agent ↔ tools (conditional loop while fetching)
agent → analyze (mode=test)
agent → save_reference (mode=set_reference)
analyze → report
report → END
save_reference → END
```

## New & Updated Files

| File | Action | Purpose |
|---|---|---|
| `infra/storage.py` | **Create** | Thin abstraction for saving/loading reference snapshots (JSON on disk). Swappable for DB later. |
| `app/qa_utils.py` | **Create** | Deterministic surface checks: broken links, broken images, missing assets. |
| `app/graph.py` | **Update** | Expand `AgentState`, new nodes (`analyze`, `report`, `save_reference`), new graph edges. |
| `app/tools/__init__.py` | **Update** | Export any new tools if needed. |
| `main.py` | **Update** | Add `--set-reference` / `--test` CLI flags (or interactive prompt). |
| `tests/infra/test_storage.py` | **Create** | Roundtrip tests for storage layer. |
| `tests/app/test_qa_utils.py` | **Create** | Tests for deterministic link/image checker. |

## Reference Snapshot Format (JSON)
Stored per URL (normalized to a safe filename):

```json
{
  "url": "https://example.com",
  "html": "...raw html...",
  "screenshot": "data:image/png;base64,...",
  "saved_at": "2024-01-01T00:00:00"
}
```

## CSV Report Format (`qa_report.csv`)

```csv
URL,Issue Type,Description,Category
https://example.com/logo.png,broken_image,404 Not Found,backend
https://example.com/,layout_shift,Header overlaps nav,frontend
```

## AgentState Expansion

```python
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    url: str
    mode: str            # "set_reference" | "test"
    html: str            # current page raw HTML
    screenshot: str      # current page base64 PNG
    issues: list[dict]   # accumulated findings
    report_path: str     # path to output CSV
```

## Future TODOs (Code Comments)
- Multi-page crawling (depth > 1)
- Functional testing (form filling, button clicking, redirects)
- Browser console error capture via Playwright
- Performance / load-time checks
- Database-backed storage instead of JSON files

## LLM Strategy
- **System Prompt:** Defines the agent as a QA tester. In `test` mode, it receives both the current and reference screenshots (base64 data URIs) plus current HTML and is asked to visually + structurally compare for abnormalities.
- **Vision:** Base64 screenshots are passed to the model as image content.

## Build Order
1. `infra/storage.py`
2. `app/qa_utils.py`
3. Update `app/graph.py` (new state + nodes + edges)
4. Update `main.py` (CLI)
5. Tests
6. Verification & review
