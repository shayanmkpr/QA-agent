# QA Tester Agent — Architecture

## Overview
Two modes: `--set-reference` captures a baseline snapshot (HTML + screenshot), `--test` compares the live page against it and outputs `qa_report.csv`.

## Graph Topology
```
Entry → agent (fetches page via browser tools)
agent ↔ tools (conditional loop)
agent → save_reference (mode=set_reference) → END
agent → analyze (mode=test) → report → END
```

## Nodes
| Node | Purpose |
|---|---|
| `agent` | Invokes LLM with system prompt + tool bindings. Decides which tools to call. |
| `tools` | `ToolNode` executing `fetch_html`, `fetch_content`, `webpage_screenshot`, `screenshot`. |
| `save_reference` | Extracts HTML + screenshot from ToolMessages, hands them to `infra.storage.save_reference()`. |
| `analyze` | Runs `check_resources()` (deterministic) + `_llm_compare()` (vision diff). |
| `report` | Writes `qa_report.csv` with columns: URL, Issue Type, Description, Category. |

## AgentState
| Field | Type | Purpose |
|---|---|---|
| `messages` | `list[BaseMessage]` | Accumulated conversation |
| `url` | `str` | Target page URL |
| `mode` | `str` | `set_reference` or `test` |
| `html` | `str` | Raw HTML from `fetch_html` |
| `screenshot` | `str` | Base64 PNG from `webpage_screenshot` |
| `issues` | `list[dict]` | Accumulated findings |
| `report_path` | `str` | Output CSV path |

## Infrastructure Layer

### `infra/storage.py`
Thin abstraction for save/load/exists over JSON files in `./data/`. Filenames are SHA256 hashes of URLs. Swappable for a database without touching the app layer.

### `infra/browser.py`
Singleton Playwright Chromium manager. Existing — unchanged.

## Deterministic Checks (`app/qa_utils.py`)
Runs HEAD requests against `href`, `src` attributes in `<a>`, `<img>`, `<link>`, `<script>`. Flags 4xx/5xx/timeout as issues. Categorized as `backend`.

## LLM Vision Comparison (`_llm_compare`)
Passes reference and current screenshots (base64 data URIs) to the LLM. Asks for visual diff: layout shifts, missing elements, color/font changes. Falls back to empty list if vision not supported.

## CSV Report (`qa_report.csv`)
```csv
URL,Issue Type,Description,Category
https://example.com/logo.png,broken_image,HTTP 404,backend
https://example.com/,layout_shift,Header overlaps nav,frontend
```

## CLI Usage
```bash
python main.py --set-reference --url https://example.com
python main.py --test --url https://example.com
```

## Extension Points (TODOs in code)
- Multi-page crawling (`app/graph.py:73`)
- Browser console error capture (`app/graph.py:74`)
- Performance / load-time checks (`app/graph.py:75`)
- Functional testing (form filling, button clicks) (`app/qa_utils.py:3`)
- CORS header checks (`app/qa_utils.py:3`)
- DB-backed storage (`infra/storage.py:3`)

## Tests
- `tests/tools/` — existing tool tests (23 tests)
- `tests/infra/test_storage.py` — save/load roundtrip (3 tests)
- `tests/app/test_qa_utils.py` — deterministic checker (4 tests)
