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
from app.tools import (  # , screenshot
    click_link,
    fetch_content,
    fetch_html,
    fill_form,
    webpage_screenshot,
    write_report,
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


# LLM with tool binding for the agent loop.
# Plain LLM (no tools) is used for vision comparison so it doesn't try to call tools.
tools = [
    click_link,
    fill_form,
    fetch_html,
    fetch_content,
    webpage_screenshot,
    write_report,
]  # , screenshot
tool_choice = os.getenv("TOOL_CHOICE") or None  # "any" for backends that reject "auto"
llm = get_llm().bind_tools(tools, tool_choice=tool_choice)
llm_plain = get_llm()


def _system_prompt(mode: str) -> str:
    if mode == "set_reference":
        return (
            "You are a QA testing assistant. Capture a reference snapshot of the target page. "
            "Fetch its raw HTML and take a full-page screenshot. Do exactly these two steps "
            "and nothing more."
        )
    return (
        "You are a QA testing assistant. Fetch the current HTML and a full-page screenshot "
        "of the target page so it can be compared against a saved reference. "
        "Use the minimum number of tool calls needed. Do not fetch multiple things in parallel "
        "unless necessary."
    )


def _extract_tool_results(messages: list[BaseMessage]) -> tuple[str, str]:
    """Pull the latest HTML and screenshot from completed tool calls."""
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
            SystemMessage(content=_system_prompt(state["mode"])),
            HumanMessage(content=f"URL: {state['url']}"),
        ]
    else:
        messages = state["messages"]

    response = llm.invoke(messages)
    return {"messages": [response]}


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
    """Ask the LLM to visually compare current vs reference screenshots."""
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
        # Vision may not be supported by the configured model / provider — degrade gracefully.
        return []

    text = response.content.strip()
    # Strip markdown code fences if present
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

    # Deterministic surface checks
    issues = check_resources(html, state["url"])

    # Reference comparison
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


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

builder = StateGraph(AgentState)

builder.add_node("agent", agent)
builder.add_node("tools", ToolNode(tools))
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
builder.add_edge("tools", "agent")
builder.add_edge("save_reference", END)
builder.add_edge("analyze", "report")
builder.add_edge("report", END)

graph = builder.compile()
