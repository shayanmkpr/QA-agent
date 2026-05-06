import csv
import json
import os
import time as _time
from pathlib import Path
from typing import Annotated, TypedDict

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from app.qa_utils import check_resources, compress_image
from app.tools import (
    click_link,
    fetch_content,
    fetch_html,
    fill_form,
    webpage_screenshot,
    write_report,
    clear_session,
    scroll_down,
    scroll_to_top,
    compact_context,
)
from infra import storage
from infra.browser import get_browser_manager
from infra.config import get_llm
from infra.logging import _log, _trunc


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    url: str
    mode: str  # "set_reference" | "test"
    html: str
    screenshot: str
    issues: list[dict]
    report_path: str
    credentials: dict


# Tools the LLM agent can call during interaction — navigate is excluded
# because the graph handles navigation deterministically.
_interaction_tools = [
    click_link,
    fill_form,
    fetch_html,
    fetch_content,
    webpage_screenshot,
    write_report,
    clear_session,
    scroll_down,
    scroll_to_top,
    compact_context,
]
_interaction_tool_map = {t.name: t for t in _interaction_tools}


def _system_prompt(mode: str, credentials: dict) -> str:
    creds_text = ""
    if credentials:
        creds_text = (
            "Available credentials:\n"
            + "\n".join(f"  - {k}: {json.dumps(v)}" for k, v in credentials.items())
            + "\n\n"
        )

    scan_instructions = (
        "Scanning & context management:\n"
        "- The page HTML and a full-page screenshot have already been captured. "
        "Use fetch_content() or the existing screenshot to scan for elements.\n"
        "- To find something not in the visible area, use scroll_down() then "
        "call webpage_screenshot() to see the new viewport. Repeat until you "
        "find it or reach the bottom (at_bottom=true).\n"
        "- Use scroll_to_top() to go back up.\n"
        "- IMPORTANT: call compact_context(summary) AFTER each scan but BEFORE "
        "clicking or interacting. This removes old screenshots and HTML from "
        "context to save tokens. Summary should describe what you found.\n"
        "- Never keep multiple screenshots or HTML dumps in context.\n\n"
        "Valid CSS selectors for click_link and fill_form:\n"
        "- Standard CSS: 'button', '.class-name', '#element-id', 'a[href=\"/login\"]'\n"
        "- Playwright text selectors: 'text=Login', 'button:has-text(\"Sign In\")'\n"
        "- Avoid jQuery-only selectors like :contains() — they don't work.\n"
    )

    if mode == "set_reference":
        return (
            "You are a QA testing assistant with a persistent browser session. "
            "The target page has already been loaded, and its HTML + screenshot "
            "have been captured.\n\n"
            f"{creds_text}"
            "Your goal: ensure we have a clean reference snapshot.\n\n"
            "If credentials are available AND the page requires authentication: "
            "scan for a login link/button, click it, fill the form using "
            "credentials, submit. Then call fetch_html() and webpage_screenshot() "
            "to capture the authenticated page.\n\n"
            f"{scan_instructions}"
            "If no login is needed, call compact_context('Page loaded, no login required') "
            "and stop."
        )
    return (
        "You are a QA testing assistant with a persistent browser session. "
        "The target page has already been loaded, and its HTML + screenshot "
        "have been captured.\n\n"
        f"{creds_text}"
        "Your goal: test the target page against the saved reference.\n\n"
        "If credentials are available AND the page requires authentication: "
        "scan for a login link/button, click it, fill the form using "
        "credentials, submit. Then call fetch_html() and webpage_screenshot() "
        "to capture the authenticated page.\n\n"
        f"{scan_instructions}"
        "If no login is needed, call compact_context('Page loaded, no login required') "
        "and stop."
    )


def _extract_tool_results(messages: list[BaseMessage]) -> tuple[str, str]:
    html = ""
    screenshot = ""
    for msg in messages:
        if isinstance(msg, ToolMessage):
            if getattr(msg, "name", None) == "fetch_html":
                html = msg.content
            elif getattr(msg, "name", None) == "webpage_screenshot":
                screenshot = msg.content
    return html, screenshot


# ---------------------------------------------------------------------------
# Deterministic nodes — no LLM, cannot loop
# ---------------------------------------------------------------------------


def navigate_node(state: AgentState) -> dict:
    """Navigate to the target URL. Deterministic, no LLM involved."""
    url = state["url"]
    _log("[navigate]", f"navigating to {url}…")
    mgr = get_browser_manager()
    start = _time.time()
    mgr.navigate(url)
    page = mgr.get_page()
    _log("[navigate]", f"loaded {page.url} ({_time.time() - start:.1f}s)", title=page.title())
    return {
        "messages": [
            AIMessage(content=f"Navigated to {page.url} (title: {page.title()})")
        ]
    }


def capture_node(state: AgentState) -> dict:
    """Fetch HTML and screenshot. Deterministic, no LLM involved."""
    _log("[capture]", "fetching HTML and screenshot…")
    mgr = get_browser_manager()
    start = _time.time()

    html = mgr.get_current_html()
    if len(html) > 100_000:
        html = html[:100_000] + "\n\n[truncated]"

    raw_screenshot = mgr.screenshot_current()
    screenshot = compress_image(raw_screenshot) if raw_screenshot.startswith("data:image") else raw_screenshot

    _log("[capture]", f"done ({_time.time() - start:.1f}s)", html_len=len(html), screenshot_kb=len(screenshot)//1024)

    return {
        "html": html,
        "screenshot": screenshot,
        "messages": [
            HumanMessage(content=(
                f"Page captured. HTML: {len(html)} chars, Screenshot: available.\n\n"
                "HTML content:\n" + html[:50000]
            )),
            AIMessage(content=f"Screenshot captured ({len(screenshot)//1024}KB base64 PNG)."),
        ],
    }


# ---------------------------------------------------------------------------
# LLM-backed nodes
# ---------------------------------------------------------------------------

_agent_llm = get_llm().bind_tools(_interaction_tools)


def agent(state: AgentState) -> dict:
    """LLM agent: decides interactions (login, scroll, inspect)."""
    if not state["messages"]:
        # Shouldn't happen — navigate + capture run first
        messages = [
            SystemMessage(content=_system_prompt(state["mode"], state.get("credentials", {}))),
            HumanMessage(content=f"URL: {state['url']}"),
        ]
        _log("[agent]", f"starting {state['mode']} flow (no prior messages)", url=state["url"])
    else:
        messages = [
            SystemMessage(content=_system_prompt(state["mode"], state.get("credentials", {}))),
        ] + list(state["messages"])
        _log("[agent]", f"thinking (context: {len(messages)} messages)…")

    response = _agent_llm.invoke(messages)

    if hasattr(response, "tool_calls") and response.tool_calls:
        tool_names = [tc["name"] for tc in response.tool_calls]
        _log("[agent]", f"decided to call {len(response.tool_calls)} tool(s): {tool_names}")
        for tc in response.tool_calls:
            _log("[agent]", f"  -> {tc['name']}", args=_trunc(json.dumps(tc.get('args', {}), indent=2), 300))
    else:
        _log("[agent]", "finished — no more tool calls", response=_trunc(str(response.content), 200))

    return {"messages": [response]}


def tools_node(state: AgentState) -> dict:
    """Execute tool calls from the last AIMessage synchronously."""
    last_msg = state["messages"][-1]
    tool_messages = []
    for tc in last_msg.tool_calls:
        name = tc["name"]
        _log("[tools]", f"executing {name}…", args=_trunc(json.dumps(tc.get('args', {}), indent=2), 200))
        tool_fn = _interaction_tool_map.get(name)
        try:
            start = _time.time()
            result = tool_fn.invoke(tc["args"]) if tool_fn else f"Unknown tool: {name}"
            elapsed = _time.time() - start
        except Exception as exc:
            result = f"Error: {exc}"
            elapsed = 0
            _log("[tools]", f"  FAILED: {exc}")
        result_str = str(result)
        if result_str.startswith("data:image/"):
            kb = len(result_str) // 1024
            _log("[tools]", f"  done ({elapsed:.1f}s) — screenshot {kb}KB base64")
        else:
            _log("[tools]", f"  done ({elapsed:.1f}s)", result=_trunc(result_str, 300))
        tool_messages.append(
            ToolMessage(content=result_str, tool_call_id=tc["id"], name=name)
        )
    return {"messages": tool_messages}


def compact_node(state: AgentState) -> dict:
    """Trim old screenshots and verbose HTML from context."""
    messages = state["messages"]
    summary = ""
    compact_idx = -1

    for i, msg in enumerate(messages):
        if isinstance(msg, ToolMessage) and getattr(msg, "name", None) == "compact_context":
            content = msg.content
            if "Preserved summary:" in content:
                summary = content.split("Preserved summary:", 1)[1].strip()
            compact_idx = i
            break

    if compact_idx == -1:
        return {"messages": []}

    trimmed = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            trimmed.append(msg)
            break

    trimmed.append(HumanMessage(content=f"[Context compacted] {summary}"))
    trimmed.append(AIMessage(content="Context compacted. Proceeding with the saved summary."))

    for msg in messages[compact_idx + 1:]:
        trimmed.append(msg)

    _log("[compact]", f"trimmed {len(messages)} msg -> {len(trimmed)} msg", summary=summary)
    return {"messages": trimmed}


def save_reference_node(state: AgentState) -> dict:
    html, screenshot = _extract_tool_results(state["messages"])
    if not html or not screenshot:
        _log("[save_ref]", "WARNING: empty html or screenshot — not saving")
        return {
            "html": html,
            "screenshot": screenshot,
            "messages": [AIMessage(content="Snapshot incomplete — html or screenshot missing.")],
        }
    path = storage.save_reference(state["url"], html, screenshot)
    _log("[save_ref]", "saved", path=path, html_len=len(html), screenshot_kb=len(screenshot)//1024)
    return {
        "html": html,
        "screenshot": screenshot,
        "messages": [AIMessage(content=f"Reference snapshot saved to {path}")],
    }


def _llm_compare(
    url: str,
    ref: dict,
    current_html: str,
    current_screenshot: str,
) -> list[dict]:
    ref_screenshot = compress_image(ref.get("screenshot", ""))
    current_screenshot = compress_image(current_screenshot)
    if not ref_screenshot or not current_screenshot:
        _log("[analyze]", "skipping VLM — missing screenshot", ref_ok=bool(ref_screenshot), cur_ok=bool(current_screenshot))
        return []
    prompt = (
        "You are a QA tester comparing a webpage against its reference snapshot.\n\n"
        "Look for visual and structural abnormalities such as:\n"
        "- Missing or changed elements\n"
        "- Layout shifts or broken styling\n"
        "- Color/font changes\n"
        "- New or missing content\n\n"
        "Return a JSON array of issues. Each issue must have:\n"
        '- "issue_type": string (e.g. layout_shift, missing_element, content_change)\n'
        '- "description": brief explanation\n'
        '- "category": one of frontend, backend, both\n\n'
        "If no issues are found, return an empty array []."
    )

    content_blocks = [
        {"type": "text", "text": "Reference screenshot:"},
        {"type": "image_url", "image_url": {"url": ref_screenshot}},
        {"type": "text", "text": "Current screenshot:"},
        {"type": "image_url", "image_url": {"url": current_screenshot}},
    ]
    include_html = os.getenv("INCLUDE_HTML_IN_VLM", "true").lower() != "false"
    if include_html:
        content_blocks.append({
            "type": "text",
            "text": (
                f"Current HTML length: {len(current_html)} chars. "
                f"Reference HTML length: {len(ref.get('html', ''))} chars."
            ),
        })

    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content=content_blocks),
    ]

    try:
        response = get_llm().invoke(messages)
    except Exception:
        return []

    text = response.content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0].strip()
    if text.startswith("json"):
        text = text[4:].strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            for issue in parsed:
                issue.setdefault("url", url)
            return parsed
    except Exception:
        pass

    return []


def analyze_node(state: AgentState) -> dict:
    html, screenshot = _extract_tool_results(state["messages"])
    if not html:
        html = state.get("html", "")
    if not screenshot:
        screenshot = state.get("screenshot", "")

    _log("[analyze]", "running deterministic checks…")
    issues = check_resources(html, state["url"])
    _log("[analyze]", f"resource check found {len(issues)} issue(s)")

    reference = storage.load_reference(state["url"])
    if reference:
        _log("[analyze]", "running LLM visual comparison against reference…")
        llm_issues = _llm_compare(state["url"], reference, html, screenshot)
        _log("[analyze]", f"VLM comparison found {len(llm_issues)} issue(s)")
        issues.extend(llm_issues)
    else:
        _log("[analyze]", "no reference — skipping VLM comparison")
        issues.append({
            "url": state["url"],
            "issue_type": "missing_reference",
            "description": "No reference snapshot found. Run with --set-reference first.",
            "category": "both",
        })

    _log("[analyze]", f"total: {len(issues)} issue(s)")
    return {"html": html, "screenshot": screenshot, "issues": issues}


def report_node(state: AgentState) -> dict:
    report_path = Path("qa_report.csv")
    issues = state.get("issues", [])
    with open(report_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["URL", "Issue Type", "Description", "Category"])
        for issue in issues:
            writer.writerow([
                issue.get("url", ""),
                issue.get("issue_type", ""),
                issue.get("description", ""),
                issue.get("category", ""),
            ])
    _log("[report]", f"wrote {len(issues)} issue(s) to {report_path}")
    return {"report_path": str(report_path)}


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def route_after_agent(state: AgentState) -> str:
    last_msg = state["messages"][-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        _log("[router]", "agent -> tools")
        return "tools"
    target = "save_reference" if state["mode"] == "set_reference" else "analyze"
    _log("[router]", f"agent -> {target}")
    return target


def route_after_tools(state: AgentState) -> str:
    for msg in reversed(state["messages"]):
        if isinstance(msg, ToolMessage):
            target = "compact" if getattr(msg, "name", None) == "compact_context" else "agent"
            _log("[router]", f"tools -> {target}")
            return target
    return "agent"


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

builder = StateGraph(AgentState)

builder.add_node("navigate", navigate_node)
builder.add_node("capture", capture_node)
builder.add_node("agent", agent)
builder.add_node("tools", tools_node)
builder.add_node("compact", compact_node)
builder.add_node("save_reference", save_reference_node)
builder.add_node("analyze", analyze_node)
builder.add_node("report", report_node)

builder.set_entry_point("navigate")
builder.add_edge("navigate", "capture")
builder.add_edge("capture", "agent")

builder.add_conditional_edges(
    "agent",
    route_after_agent,
    {
        "tools": "tools",
        "save_reference": "save_reference",
        "analyze": "analyze",
    },
)
builder.add_conditional_edges(
    "tools",
    route_after_tools,
    {
        "compact": "compact",
        "agent": "agent",
    },
)
builder.add_edge("compact", "agent")
builder.add_edge("save_reference", END)
builder.add_edge("analyze", "report")
builder.add_edge("report", END)

graph = builder.compile()
