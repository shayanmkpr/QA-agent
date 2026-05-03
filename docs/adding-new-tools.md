# Adding a New Tool to the LangGraph Agent

A LangChain tool is a typed Python function, decorated with `@tool`, that the LLM can invoke during the agent loop by emitting a `tool_call`. The `ToolNode` receives the call, executes the function, appends a `ToolMessage` to `AgentState.messages`, and returns control to the LLM node.



## Context

- **Upstream caller**: `main.py` invokes `graph.invoke({"url": url})`.
- **Graph wiring**: `app/graph.py` defines `AgentState`, assembles the `tools` list, binds it to the LLM via `get_llm().bind_tools(tools)`, and wires a `ToolNode`.
- **Downstream**: The `ToolNode` maps `tool_call["name"]` to the registered function by name, passing `tool_call["args"]` as keyword arguments.

## Step-by-Step Guide

### Step 1: Create a new file under `app/tools/`

Import `tool` from `langchain_core.tools` and decorate a typed function.

```python
# app/tools/read_file.py
from pathlib import Path
from langchain_core.tools import tool

@tool
def my_tool(arg: str) -> str:
    """Description the LLM uses to decide when to call this tool."""
    return f"result: {arg}"
```

### Step 2: Write a descriptive docstring

The docstring is embedded into the JSON schema sent to the LLM as the tool description. Describe:
- **When** to use the tool.
- **What each argument means**.
- **What the return value contains**.

Ambiguous or terse docstrings cause the LLM to skip the tool or hallucinate arguments.

### Step 3: Register in `app/graph.py`

Import the function and append it to the `tools` list:

```python
from app.tools import fetch_html, screenshot, my_tool

tools = [fetch_html, screenshot, my_tool]
```

`bind_tools(tools)` and `ToolNode(tools)` both derive their behavior from this list. No other graph wiring is required.

### Step 4: Add dependencies to `requirements.txt`

If the tool requires a new package, append it:

```text
some-package>=1.0.0
```

### Step 5: Run and test

```bash
python main.py
```

Verify in the trace that the LLM emits a `tool_call` for the new tool and that the `ToolNode` returns the expected result.

## Tool Function Requirements

- **Type hints are mandatory**: `bind_tools` introspects annotations to build the JSON schema. Untyped arguments default to `Any` and reduce call accuracy.
- **Return a serializable value**: Prefer `str`, `int`, `float`, `bool`, `dict`, or `list`. The return value becomes the `content` of the `ToolMessage` sent back to the LLM.
- **Handle errors inside the function**: Uncaught exceptions bubble up through `ToolNode` and crash the graph. Return an error string or raise a specific exception only if you have an outer retry policy.

```python
@tool
def risky_operation(path: str) -> str:
    """Read a file safely."""
    try:
        with open(path, "r") as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: file not found at {path}"
```

## Example: Calculator Tool

```python
# app/tools/calculate.py
from langchain_core.tools import tool

@tool
def calculate(expression: str) -> str:
    """Evaluate a simple math expression and return the result.
    
    Use this for arithmetic, percentages, or unit conversions.
    Expression must use standard Python math syntax.
    """
    try:
        # Restrict to safe builtins only
        allowed = {"__builtins__": None}
        result = eval(expression, allowed, {})
        return str(result)
    except Exception as exc:
        return f"Calculation error: {exc}"
```

```python
# app/graph.py
from app.tools import fetch_html, screenshot, calculate

tools = [fetch_html, screenshot, calculate]
```

## Example: File Reader Tool

```python
# app/tools/calculate.py
from langchain_core.tools import tool

ALLOWED_ROOT = Path("./data")

@tool
def read_file(path: str) -> str:
    """Read the contents of a text file under the ./data directory.
    
    Args:
        path: Relative path inside ./data, e.g. "orders/123.txt".
    """
    target = (ALLOWED_ROOT / path).resolve()
    if not str(target).startswith(str(ALLOWED_ROOT.resolve())):
        return "Error: path traversal blocked."
    if not target.exists():
        return f"Error: {path} does not exist."
    return target.read_text(encoding="utf-8")
```

Filesystem access should always resolve the real path and enforce an allow-list root to prevent traversal.

## URL validation for HTTP-fetching tools

Any tool that fetches or screenshots a remote URL must guard against SSRF before delegating to the browser layer. Use `app.tools._url._validate_url` at the top of the tool function:

```python
from app.tools._url import _validate_url

@tool
def my_fetch_tool(url: str) -> str:
    _validate_url(url)
    return get_browser_manager().get_html(url)
```

`_validate_url` enforces three invariants:

1. **Scheme restriction** — Only `http` and `https` are permitted.
2. **Loopback block** — Hostnames such as `localhost`, `127.0.0.1`, `::1`, and `0.0.0.0` are rejected.
3. **IP range block** — IPv4/IPv6 addresses in private, loopback, reserved, or unspecified ranges are rejected.

If validation fails, a `ValueError` is raised. Let it propagate so the graph-level error policy surfaces it to the LLM.

## How the LLM Decides to Call a Tool

During `llm.invoke(state["messages"])`, the model receives a system prompt plus the list of tool schemas derived from the `tools` list. The schema includes the function name, argument types, and the docstring as the description. The model decides:

1. Whether any tool is relevant to the user query or prior context.
2. Which tool to call.
3. The exact arguments conforming to the schema.

If multiple tools are available, the LLM relies entirely on the docstring to disambiguate. Names like `read_file` are less important than the description text. If the LLM fails to call the correct tool, rewrite the docstring to make the trigger condition explicit.

## Extending AgentState

If a tool needs to persist structured data beyond the message list (e.g., an extracted entity or an intermediate file path), add a field to `AgentState`:

```python
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    url: str
    html: str
    extracted_data: str
```

Update the node functions to read or write that field. `ToolNode` only mutates `messages`; any other state updates must be done by a custom node or by having the `agent` node branch based on `ToolMessage` content.

## Testing Tools Independently

You do not need to invoke the full graph to test a tool. Import the function and call it directly:

```python
from app.tools import read_file

result = read_file("orders/123.txt")
assert "customer" in result
```

For tools that rely on graph state, mock the arguments as plain Python values. This is faster than running the graph and avoids consuming LLM tokens during debugging.
