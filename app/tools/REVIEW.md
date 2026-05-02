# Diff Review Summary

## `app/tools/` refactor (deleted `tools.py`, split into package)

- **`fetch_html.py`**, **`fetch_content.py`**, **`webpage_screenshot.py`**  
  `FIXME: No URL validation — accepts file://, internal hosts, and SSRF vectors.`  
  **Fix:** Add allow-list / scheme validation before passing `url` to `get_browser_manager()`.

- **`screenshot.py`**  
  `FIXME: Bare except Exception — masks unrelated failures and complicates debugging.`  
  **Fix:** Catch specific `PIL` exceptions (e.g., `OSError`) only.

- **`requirements.txt`**  
  Cleaned duplicate entries; no issue.

## Architecture

Modular split is correct. No logic changes introduced beyond moved code.
