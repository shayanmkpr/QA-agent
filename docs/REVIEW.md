# Review Summary

## `app/graph.py`

- ✅ **SSRF covered** — all fetch tools call `_validate_url()` before browser access.
- ✅ **Vision fallback** — `_llm_compare()` wraps the vision call in try/except; degrades to `[]` if the model/provider doesn't support it.
- ✅ **Deterministic + LLM checks** — `analyze_node` runs `check_resources()` first (fast, no tokens), then the LLM comparison for visual diff.
- ⚠️ **Rate of HTTP requests** — `check_resources()` makes a HEAD/GET for every `<a>`, `<img>`, `<link>`, `<script>` on the page. On a page with 500 links this fires 500 sequential requests. For expensive pages this can take minutes.

### `app/qa_utils.py`

- ⚠️ **Concurrency missing** — `_check_resource()` calls are sequential. This is fine for small pages but will bottleneck on larger ones.
- ⚠️ **Single depth only** — Only checks resources referenced directly in the HTML. No crawling of linked pages, no iframe support.
- ✅ **Timeout handling** — 10s timeout + fallback HEAD→GET on 405.

### `infra/storage.py`

- ✅ **Clean abstraction** — `save_reference`, `load_reference`, `reference_exists`. No app code touches files directly.
- ✅ **Safe filenames** — SHA256 hash of URL avoids path traversal.

### `main.py`

- ✅ **CLI interface** — `--set-reference` and `--test` flags. Fallback to interactive prompt when no flags given.
