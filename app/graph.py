import csv
import json
import os
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
from langgraph.prebuilt import ToolNode

from app.qa_utils import check_resources, compress_image
from app.tools import (
    navigate,
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
from infra.config import get_llm


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    url: str
    mode: str  # "set_reference" | "test"
    html: str
    screenshot: str
    issues: list[dict]
    report_path: str
    credentials: dict


tools = [
    navigate,
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
tool_choice = os.getenv("TOOL_CHOICE") or None
llm = get_llm().bind_tools(tools, tool_choice=tool_choice)
llm_plain = get_llm()


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
        "- When you need to find something on the page (a link, button, form, etc.), "
        "first check the visible area: call webpage_screenshot() and/or fetch_content() "
        "to see the current viewport.\n"
        "- If you don't see what you need, use scroll_down() to move down the page. "
        "Check again with screenshot/content. Repeat until you find it or reach "
        "the bottom (scroll_down reports at_bottom=true).\n"
        "- If you need to go back up, use scroll_to_top() then scroll_down() to "
        "scan again.\n"
        "- IMPORTANT: once you find what you were looking for, call compact_context(summary) "
        "BEFORE clicking or interacting. This removes old screenshots and HTML dumps "
        "from context to save tokens. The summary should describe what you found, "
        "where it is, and what action you'll take next.\n"
        "- Never keep multiple screenshots or HTML dumps in context. "
        "Compact after each successful scan."
    )

    if mode == "set_reference":
        return (
            "You are a QA testing assistant with a persistent browser session. "
            "Browser state (cookies, localStorage) survives across tool calls — "
            "use navigate() first, then interact with the page.\n\n"
            f"{creds_text}"
            "Your goal: capture a reference snapshot of the target page.\n\n"
            "Workflow:\n"
            "1. Navigate to the target URL.\n"
            "2. If credentials are available and the page requires authentication, "
            "examine the page for a login link/button. If you don't see it in the "
            "current view, scan the page by scrolling down until you find it. "
            "Click it, find the login form, fill in email/password using credentials, "
            "and submit. Verify authenticated content.\n"
            "3. Fetch the raw HTML and take a full-page screenshot.\n"
            f"{scan_instructions}"
            "Do exactly what is needed — no more, no less."
        )
    return (
        "You are a QA testing assistant with a persistent browser session. "
        "Browser state (cookies, localStorage) survives across tool calls — "
        "use navigate() first, then interact with the page.\n\n"
        f"{creds_text}"
        "Your goal: test the target page against a saved reference.\n\n"
        "Workflow:\n"
        "1. Navigate to the target URL.\n"
        "2. If credentials are available, log in: examine the page for a login "
        "link/button. If not visible, scan by scrolling until you find it. "
        "Click it, find the form, fill credentials, submit, verify success.\n"
        "3. Fetch the current HTML and a full-page screenshot for comparison.\n"
        f"{scan_instructions}"
        "Use the minimum number of tool calls needed."
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
# Nodes
# ---------------------------------------------------------------------------


def agent(state: AgentState) -> dict:
    if not state["messages"]:
        messages = [
            SystemMessage(content=_system_prompt(state["mode"], state.get("credentials", {}))),
            HumanMessage(content=f"URL: {state['url']}"),
        ]
    else:
        messages = state["messages"]

    response = llm.invoke(messages)
    return {"messages": [response]}


def compact_node(state: AgentState) -> dict:
    """Trim old screenshots and verbose HTML from context, keeping only
    the compact_context summary and recent essential messages."""
    messages = state["messages"]
    summary = ""
    compact_idx = -1

    # Find the compact_context ToolMessage
    for i, msg in enumerate(messages):
        if isinstance(msg, ToolMessage) and getattr(msg, "name", None) == "compact_context":
            # Extract summary from the tool result
            content = msg.content
            if "Preserved summary:" in content:
                summary = content.split("Preserved summary:", 1)[1].strip()
            compact_idx = i
            break

    if compact_idx == -1:
        return {"messages": []}

    # Keep: system message + summary + messages after the compact_context call
    trimmed = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            trimmed.append(msg)
            break

    trimmed.append(HumanMessage(content=f"[Context compacted] {summary}"))
    trimmed.append(AIMessage(content="Context compacted. Proceeding with the saved summary."))

    # Keep messages that came after the compact_context result
    for msg in messages[compact_idx + 1:]:
        trimmed.append(msg)

    return {"messages": trimmed}


# TODO: add multi-page crawling support (depth > 1)
# TODO: capture browser console errors via Playwright
# TODO: add performance / load-time checks


def save_reference_node(state: AgentState) -> dict:
    html, screenshot = _extract_tool_results(state["messages"])
    path = storage.save_reference(state["url"], html, screenshot)
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
        content_blocks.append(
            {
                "type": "text",
                "text": (
                    f"Current HTML length: {len(current_html)} chars. "
                    f"Reference HTML length: {len(ref.get('html', ''))} chars."
                ),
            }
        )
    print(f"[_llm_compare] HTML included in VLM prompt: {include_html}")

    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content=content_blocks),
    ]

    try:
        response = llm_plain.invoke(messages)
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

    issues = check_resources(html, state["url"])

    reference = storage.load_reference(state["url"])
    if reference:
        llm_issues = _llm_compare(state["url"], reference, html, screenshot)
        issues.extend(llm_issues)
    else:
        issues.append(
            {
                "url": state["url"],
                "issue_type": "missing_reference",
                "description": "No reference snapshot found. Run with --set-reference first.",
                "category": "both",
            }
        )

    return {"html": html, "screenshot": screenshot, "issues": issues}


def report_node(state: AgentState) -> dict:
    report_path = Path("qa_report.csv")
    with open(report_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["URL", "Issue Type", "Description", "Category"])
        for issue in state.get("issues", []):
            writer.writerow(
                [
                    issue.get("url", ""),
                    issue.get("issue_type", ""),
                    issue.get("description", ""),
                    issue.get("category", ""),
                ]
            )
    return {"report_path": str(report_path)}


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def route_after_agent(state: AgentState) -> str:
    last_msg = state["messages"][-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "tools"
    if state["mode"] == "set_reference":
        return "save_reference"
    if state["mode"] == "test":
        return "analyze"
    return END


def route_after_tools(state: AgentState) -> str:
    """After tools execute, check if compact_context was called.
    If so, route to compact_node to trim context before continuing."""
    for msg in reversed(state["messages"]):
        if isinstance(msg, ToolMessage):
            if getattr(msg, "name", None) == "compact_context":
                return "compact"
            break
    return "agent"


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

builder = StateGraph(AgentState)

builder.add_node("agent", agent)
builder.add_node("tools", ToolNode(tools))
builder.add_node("compact", compact_node)
builder.add_node("save_reference", save_reference_node)
builder.add_node("analyze", analyze_node)
builder.add_node("report", report_node)

builder.set_entry_point("agent")
builder.add_conditional_edges(
    "agent",
    route_after_agent,
    {
        "tools": "tools",
        "save_reference": "save_reference",
        "analyze": "analyze",
        END: END,
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