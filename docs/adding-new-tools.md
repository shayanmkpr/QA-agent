# Adding a New Tool

A LangChain tool is a typed Python function decorated with `@tool`. The LLM can invoke it by emitting a `tool_call`. The `tools_node` in the graph (or the inline executor in the chat loop) executes the function and appends a `ToolMessage` to the conversation.

## Where tools are wired

All tools are registered in a single place:

| Tool set | Location | Used by |
|---|---|---|
| `_TOOLS` | `main.py:78` | Interactive REPL agent |

The REPL agent binds **all** tools (including `navigate`) since every
interaction is user-driven.

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

### Step 3: Register the tool

**In `app/tools/__init__.py`**: import and add to `__all__`:

```python
from app.tools.my_tool import my_tool

__all__ = [..., "my_tool"]
```

**In `main.py`**: import and add to `_TOOLS`:

```python
from app.tools import my_tool

_TOOLS = [..., my_tool]
```

Also add it to the scenario runner's tool set if applicable:

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
# In app/tools/__init__.py:
from app.tools.calculate import calculate
# add "calculate" to __all__

# In main.py:
from app.tools import calculate
_TOOLS = [..., calculate]
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

## URL validation

If your tool accepts a URL, validate it with `_validate_url` before use:

```python
from app.tools._url import _validate_url

@tool
def my_fetch_tool(url: str) -> str:
    _validate_url(url)
    return get_browser_manager().navigate(url)
```

`_validate_url` blocks non-HTTP(S) schemes, localhost, loopback, and private IP ranges.

## How the LLM Decides to Call a Tool

During `llm.invoke(state["messages"])`, the model receives a system prompt plus the list of tool schemas derived from the `tools` list. The schema includes the function name, argument types, and the docstring as the description. The model decides:

1. Whether any tool is relevant to the user query or prior context.
2. Which tool to call.
3. The exact arguments conforming to the schema.

If multiple tools are available, the LLM relies entirely on the docstring to disambiguate. Names like `read_file` are less important than the description text. If the LLM fails to call the correct tool, rewrite the docstring to make the trigger condition explicit.

## Prompt templates

All agent prompts live in `prompts/templates.py` as pure functions that take
keyword parameters.  No prompt text is hardcoded in consumer modules.

```python
from prompts.templates import qa_agent_system

system = qa_agent_system(credentials_display="{...}")
```

To override a prompt, store it in the database:

```python
from infra.db import get_db

get_db().set_prompt("system", "You are a custom QA agent...")
```

The agent will prefer the DB-stored template over the code default.

## Testing Tools Independently

You do not need to invoke the full graph to test a tool. Import the function and call it directly:

```python
from app.tools import read_file

result = read_file("orders/123.txt")
assert "customer" in result
```

For tools that rely on graph state, mock the arguments as plain Python values. This is faster than running the graph and avoids consuming LLM tokens during debugging.
