# screenshot tool

The `screenshot` tool captures the host screen as a base64-encoded PNG data URI, enabling the LLM-agent to perceive the user's desktop state when grounded vision input is required.

## Context

- **Upstream callers:** LangGraph `ToolNode` (`app/graph.py`) invokes this tool when the LLM emits a `tool_call` named `screenshot`.
- **Downstream dependencies:** `PIL.ImageGrab` from Pillow (`Pillow>=10.0.0`).
- **Runtime environment:** The tool executes in the same Python process as the agent graph on the user's local machine. Screen capture requires OS-level permission (e.g., macOS Screen Recording).

## How it works

1. **Capture:** `PIL.ImageGrab.grab()` performs a blocking grab of the primary display. It returns an RGB `Image`.
2. **Serialize:** The image is written to an in-memory `io.BytesIO` buffer in PNG format (`img.save(buffer, format="PNG")`).
3. **Encode:** The PNG bytes are base64-encoded (`base64.b64encode`) and decoded to a UTF-8 string.
4. **Wrap:** The tool returns a single string prefixed with the data URI scheme: `data:image/png;base64,<encoded-data>`.

## Graph integration

In `app/graph.py`, `screenshot` is imported alongside `fetch_html` and placed in the `tools` list:

```python
from app.tools import fetch_html, screenshot
tools = [fetch_html, screenshot]
llm = get_llm().bind_tools(tools)
```

The LLM auto-discovers the tool through `.bind_tools(tools)`. When the model decides a screenshot is needed, it emits a `tool_call` targeting `screenshot`. The LangGraph `ToolNode(tools)` routes the call, executes `screenshot()`, and appends the result (a `ToolMessage`) to the conversation state. Control then flows back to the `agent` node.

## Error handling

`ImageGrab.grab()` is wrapped in a bare `try/except` because OS-level screen capture permissions vary by platform. On macOS, if the terminal process lacks Screen Recording permission, `grab()` raises an exception. Instead of propagating a raw traceback, the tool returns a user-facing message:

```
[screenshot failed: <exception details>]

Hint: On macOS, grant the terminal app Screen Recording permission in 
System Settings > Privacy & Security > Screen Recording.
```

This string becomes the `content` of the `ToolMessage`. The LLM receives it in the next `agent` invocation and can adjust its response or ask the user to rectify the permission state.

## Return format

**Success:** a single string matching the exact pattern:

```
data:image/png;base64,<base64-encoded-png-bytes>
```

**Failure:** a single string containing the failure reason and platform-specific remediation hint.

**Consumers:** Vision-capable models (e.g., GPT-4o) can ingest `data:image/png;base64,...` URIs directly as message content. Non-vision models or logging layers should render or persist the string as a diagnostic artifact. The format contains no additional metadata; the entire payload is the URI string itself.
