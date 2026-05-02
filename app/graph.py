from typing import Annotated, TypedDict
import csv
import json
from pathlib import Path

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage, ToolMessage

from infra.config import get_llm
from infra import storage
from app.tools import fetch_html, fetch_content, webpage_screenshot, screenshot
from app.qa_utils import check_resources


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
tools = [fetch_html, fetch_content, webpage_screenshot, screenshot]
llm = get_llm().bind_tools(tools)
llm_plain = get_llm()


def _system_prompt(mode: str) -> str:
    if mode == "set_reference":
        return (
            "You are a QA testing assistant. Capture a reference snapshot of the target page. "
            "Fetch its raw HTML and take a full-page screenshot."
        )
    return (
        "You are a QA testing assistant. Fetch the current HTML and a full-page screenshot "
        "of the target page so it can be compared against a saved reference."
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
    ref_screenshot = ref.get("screenshot", "")
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

    messages = [
        SystemMessage(content=prompt),
        HumanMessage(
            content=[
                {"type": "text", "text": "Reference screenshot:"},
                {"type": "image_url", "image_url": {"url": ref_screenshot}},
                {"type": "text", "text": "Current screenshot:"},
                {"type": "image_url", "image_url": {"url": current_screenshot}},
                {
                    "type": "text",
                    "text": (
                        f"Current HTML length: {len(current_html)} chars. "
                        f"Reference HTML length: {len(ref.get('html', ''))} chars."
                    ),
                },
            ]
        ),
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
    {"tools": "tools", "save_reference": "save_reference", "analyze": "analyze", END: END},
)
builder.add_edge("tools", "agent")
builder.add_edge("save_reference", END)
builder.add_edge("analyze", "report")
builder.add_edge("report", END)

graph = builder.compile()
