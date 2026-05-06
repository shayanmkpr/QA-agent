import argparse
import json
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool as langchain_tool

from infra.validate import validate_all
from infra.config import get_llm
from infra.browser import get_browser_manager
from infra.credentials import get_credential_store
from infra.db import get_db
from infra.logging import _log, _trunc
from prompts.templates import qa_agent_system
from app.scenarios.runner import run_all_scenarios, write_scenario_report, print_summary
from app.scenarios.parser import parse_scenarios
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
    check_console_errors,
    check_network,
    hover,
)

_MAX_ROUNDS_PER_TURN = 25
_MAX_TOKENS_BEFORE_COMPACT = 100_000
_DEFAULT_SCENARIOS_FILE = "docs/scenarios.md"

# ---------------------------------------------------------------------------
# Run-scenarios tool — defined here to avoid circular import with runner
# ---------------------------------------------------------------------------

@langchain_tool
def run_scenarios(scenarios_file: str = _DEFAULT_SCENARIOS_FILE, url: str = "") -> str:
    """Run all QA scenarios from a markdown file against a target URL.

    Call this when the user asks to run test scenarios (e.g. "run all scenarios
    on https://example.com"). Parses the scenarios file, executes each one
    sequentially against the given URL, and writes a CSV report.

    Parameters:
    - scenarios_file: Path to the markdown file (default: docs/scenarios.md).
    - url: The base URL to test. Required.
    """
    if not url:
        return "Error: 'url' parameter is required — provide the base URL to test."
    file_path = Path(scenarios_file)
    if not file_path.exists():
        return f"Error: scenarios file not found at '{scenarios_file}'."
    scenarios = parse_scenarios(str(file_path))
    if not scenarios:
        return "Error: no scenarios parsed from the file."
    credentials = get_credential_store().all()
    results = run_all_scenarios(scenarios, credentials, url)
    report_path = write_scenario_report(results)
    print_summary(results)
    pass_count = sum(1 for r in results if r.status == "PASS")
    fail_count = sum(1 for r in results if r.status == "FAIL")
    error_count = sum(1 for r in results if r.status == "ERROR")
    return (
        f"Scenario run complete on {url}. "
        f"{pass_count} passed, {fail_count} failed, {error_count} errored "
        f"out of {len(results)} total. Full report: {report_path}."
    )


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

_TOOLS = [
    navigate, click_link, fill_form, hover,
    fetch_html, fetch_content, webpage_screenshot,
    scroll_down, scroll_to_top,
    check_console_errors, check_network,
    write_report, clear_session, compact_context,
    run_scenarios,
]
_TOOL_MAP = {t.name: t for t in _TOOLS}


# ---------------------------------------------------------------------------
# Context compaction
# ---------------------------------------------------------------------------

def _estimate_tokens(messages: list) -> int:
    total = 0
    for msg in messages:
        content = msg.content
        if isinstance(content, str):
            total += len(content) // 4
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and "text" in block:
                    total += len(block["text"]) // 4
    return total


def _auto_compact(messages: list, max_tokens: int = _MAX_TOKENS_BEFORE_COMPACT) -> list:
    estimated = _estimate_tokens(messages)
    if estimated < max_tokens:
        return messages
    _log("[compact]", f"auto-compacting ~{estimated:,} tokens")

    sys_idx = next((i for i, m in enumerate(messages) if isinstance(m, SystemMessage)), None)
    recent: list = []
    screenshot_found = False
    for msg in reversed(messages):
        content = str(msg.content) if hasattr(msg, "content") else ""
        if content.startswith("data:image/") and not screenshot_found:
            recent.insert(0, msg)
            screenshot_found = True
        elif not content.startswith("data:image/"):
            recent.insert(0, msg)
            if len(recent) >= 6:
                break

    compacted = [messages[sys_idx]] if sys_idx is not None else []
    compacted.append(HumanMessage(
        content="[Auto-compacted] Context cleared. The page is still loaded in the browser. "
                "Use webpage_screenshot() or fetch_content() to see current state."
    ))
    compacted.append(AIMessage(content="Understood."))
    compacted.extend(recent)
    _log("[compact]", f"{len(messages)} -> {len(compacted)} messages")
    return compacted


def _apply_compact(history: list, result_str: str) -> list:
    """Trim history when the agent called compact_context."""
    summary = ""
    if "Preserved summary:" in result_str:
        summary = result_str.split("Preserved summary:", 1)[1].strip()
    sys_msg = next((m for m in history if isinstance(m, SystemMessage)), None)
    compacted = [sys_msg] if sys_msg else []
    compacted.append(HumanMessage(content=f"[Context compacted] {summary}"))
    compacted.append(AIMessage(content="Context compacted. Proceeding."))
    _log("[compact]", f"manual compact: {len(history)} -> {len(compacted)} messages")
    return compacted


# ---------------------------------------------------------------------------
# Agent turn
# ---------------------------------------------------------------------------

def _execute_turn(history: list, llm) -> list:
    """Run LLM + tools loop for one user command. Returns updated history."""
    for round_i in range(_MAX_ROUNDS_PER_TURN):
        _log("[agent]", f"round {round_i + 1}/{_MAX_ROUNDS_PER_TURN}")

        try:
            history = _auto_compact(history)
            response = llm.invoke(history)
        except Exception as exc:
            err = str(exc)
            _log("[agent]", f"LLM error: {err}")
            if any(kw in err.lower() for kw in ("400", "context", "token")):
                history = _auto_compact(history, max_tokens=50_000)
                try:
                    response = llm.invoke(history)
                except Exception as exc2:
                    history.append(AIMessage(content=f"Context overflow: {exc2}"))
                    return history
            else:
                history.append(AIMessage(content=f"Error: {err[:500]}"))
                return history

        history.append(response)

        if not response.tool_calls:
            _log("[agent]", "done — no more tool calls")
            return history

        tool_names = [tc["name"] for tc in response.tool_calls]
        _log("[agent]", f"calling {len(response.tool_calls)} tool(s): {tool_names}")

        for tc in response.tool_calls:
            name = tc["name"]
            args = tc.get("args", {})
            _log("[agent]", f"  {name}: {_trunc(json.dumps(args), 200)}")

            fn = _TOOL_MAP.get(name)
            try:
                result = str(fn.invoke(args)) if fn else f"Unknown tool: {name}"
            except Exception as e:
                result = f"Error: {e}"
                _log("[agent]", f"  FAILED: {e}")

            if result.startswith("data:image/"):
                _log("[agent]", f"  screenshot: {len(result) // 1024}KB")
            else:
                _log("[agent]", f"  result: {_trunc(result, 300)}")

            history.append(ToolMessage(
                content=result, tool_call_id=tc["id"], name=name
            ))

            if name == "compact_context":
                history = _apply_compact(history, result)
                break

    history.append(AIMessage(content="Reached maximum rounds — stopping."))
    return history


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    validate_all()

    parser = argparse.ArgumentParser(description="QA Tester Agent — interactive REPL")
    parser.add_argument("--url", type=str, help="URL to navigate to on startup")
    args = parser.parse_args()

    _log("[main]", "initialising browser…")
    get_browser_manager().get_page()
    _log("[main]", "browser ready")

    credentials = get_credential_store().all()
    creds_display = json.dumps(credentials, indent=2) if credentials else "none"
    system = qa_agent_system(credentials_display=creds_display)

    history: list = [SystemMessage(content=system)]
    llm = get_llm().bind_tools(_TOOLS)

    if args.url:
        history.append(HumanMessage(content=f"Navigate to {args.url} and capture the page."))
        history = _execute_turn(history, llm)
        last_content = str(history[-1].content) if hasattr(history[-1], "content") else ""
        if last_content.strip():
            print(f"\nAgent: {last_content}\n")

    print("QA Agent ready. Type a command (e.g. 'click the Login button', "
          "'run scenarios on https://...'), or 'done' to exit.\n")

    try:
        while True:
            try:
                user_input = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not user_input:
                continue
            if user_input.lower() in ("done", "exit", "quit"):
                break

            _log("[main]", f"user: {_trunc(user_input, 300)}")
            history.append(HumanMessage(content=user_input))
            history = _execute_turn(history, llm)

            last = history[-1]
            content = str(last.content) if hasattr(last, "content") else str(last)
            if content.strip():
                print(f"\nAgent: {content}\n")
    finally:
        _log("[main]", "shutting down browser…")
        get_browser_manager().close()


if __name__ == "__main__":
    main()
