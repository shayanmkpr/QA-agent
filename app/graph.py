from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain_core.messages import BaseMessage

from infra.config import get_llm
from app.tools import fetch_html, fetch_content, webpage_screenshot, screenshot


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    url: str
    html: str


tools = [fetch_html, fetch_content, webpage_screenshot, screenshot]
llm = get_llm().bind_tools(tools)


def agent(state: AgentState) -> dict:
    if not state["messages"]:
        response = llm.invoke([
            {"role": "user", "content": f"Fetch the HTML content of this URL: {state['url']}"}
        ])
    else:
        response = llm.invoke(state["messages"])

    if response.tool_calls:
        return {"messages": [response]}
    return {"html": response.content, "messages": [response]}


def route(state: AgentState) -> str:
    last_msg = state["messages"][-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "tools"
    return END


builder = StateGraph(AgentState)

builder.add_node("agent", agent)
builder.add_node("tools", ToolNode(tools))

builder.set_entry_point("agent")
builder.add_conditional_edges("agent", route, {"tools": "tools", END: END})
builder.add_edge("tools", "agent")

graph = builder.compile()
