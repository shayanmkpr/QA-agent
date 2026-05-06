import argparse
import json
import time

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from infra.validate import validate_all
from infra import storage
from infra.config import get_llm
from infra.browser import get_browser_manager
from infra.credentials import get_credential_store
from infra.logging import _log, _trunc
from app.graph import graph
from app.scenarios.runner import (
    run_all_scenarios,
    write_scenario_report,
    print_summary,
)
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
)

_tools = [
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
_tool_map = {t.name: t for t in _tools}


def _estimate_tokens(messages: list) -> int:
    """Rough token estimate: ~4 chars per token."""
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


def _auto_compact(history: list, max_tokens: int = 100_000) -> list:
    """Force context compaction when approaching the token limit."""
    estimated = _estimate_tokens(history)
    if estimated < max_tokens:
        return history

    _log("[auto-compact]", f"context at ~{estimated} tokens, compacting…")

    # Find the SystemMessage
    sys_idx = None
    for i, msg in enumerate(history):
        if isinstance(msg, SystemMessage):
            sys_idx = i
            break

    # Keep only the system message and last few messages
    # Preserve the most recent screenshot if any
    recent = []
    screenshot_found = False
    for msg in reversed(history):
        content = str(msg.content) if hasattr(msg, 'content') else ""
        is_screenshot = content.startswith("data:image/")
        if is_screenshot and not screenshot_found:
            recent.insert(0, msg)
            screenshot_found = True
        elif not is_screenshot:
            recent.insert(0, msg)
            if len(recent) >= 6:
                break

    compacted = [history[sys_idx]] if sys_idx is not None else []
    compacted.append(HumanMessage(
        content="[Auto-compacted] Context was too large. "
        "Previous scan results have been cleared. The page is still loaded "
        "in the browser. Use webpage_screenshot() or fetch_content() to "
        "see the current state."
    ))
    compacted.append(AIMessage(content="Understood. I'll work with the current browser state."))
    compacted.extend(recent)

    _log("[auto-compact]", f"{len(history)} -> {len(compacted)} messages")
    return compacted


def main():
    validate_all()

    parser = argparse.ArgumentParser(description="QA Tester Agent")
    parser.add_argument("--set-reference", action="store_true",
                        help="Capture and save a reference snapshot")
    parser.add_argument("--test", action="store_true",
                        help="Run QA test against saved reference")
    parser.add_argument("--url", type=str, help="Target URL")
    parser.add_argument("--scenarios", action="store_true",
                        help="Run all QA scenarios from docs/scenarios.md")
    parser.add_argument("--scenarios-file", type=str, default="docs/scenarios.md",
                        help="Path to scenarios markdown file")
    args = parser.parse_args()

    if args.scenarios:
        url = args.url or input("URL: ").strip()
        credentials = get_credential_store().all()
        _log("[main]", "initialising browser for scenario run...")
        get_browser_manager().get_page()
        _log("[main]", f"parsing scenarios from {args.scenarios_file}...")
        scenarios = parse_scenarios(args.scenarios_file)
        _log("[main]", f"parsed {len(scenarios)} scenarios")
        results = run_all_scenarios(scenarios, credentials, url)
        report_path = write_scenario_report(results)
        print_summary(results)
        return

    url = args.url or input("URL: ").strip()

    ref_exists = storage.reference_exists(url)

    if not ref_exists:
        mode = "set_reference"
        print("No reference snapshot found. Running set-reference flow automatically.")
    elif args.set_reference:
        mode = "set_reference"
    else:
        ans = input("Reference found. Run QA test? [y/N]: ").strip().lower()
        if ans != "y":
            return
        mode = "test"

    credentials = get_credential_store().all()

    _log("[main]", "initialising browser on main thread…")
    get_browser_manager().get_page()
    _log("[main]", "browser ready")

    _log("[main]", f"invoking graph ({mode} mode)…")
    start = time.time()
    result = graph.invoke({
        "url": url,
        "mode": mode,
        "messages": [],
        "credentials": credentials,
    })
    _log("[main]", f"graph finished ({time.time() - start:.1f}s)")

    if mode == "set_reference":
        _log("[main]", "reference saved, exiting")
        print("Reference saved.")
        return

    issues = result.get("issues", [])
    _log("[main]", f"test complete: {len(issues)} issue(s)")
    print(f"Test complete — {len(issues)} issue(s) found.")

    # Keep browser alive — do NOT close it. Chat agent reuses the same page.
    print()
    print("You can now ask follow-up questions. Type 'done' to exit.")
    print()

    chat_llm = get_llm().bind_tools(_tools)

    history = [
        SystemMessage(content=(
            f"You are a QA assistant helping investigate the page {url}. "
            f"The automated test found {len(issues)} issues. "
            "The browser is already on the target page — do NOT call navigate() "
            "again unless the user asks you to go somewhere else.\n\n"
            "Available tools:\n"
            "- webpage_screenshot() — see the page visually\n"
            "- fetch_content() — read text content\n"
            "- fetch_html() — inspect page structure and find selectors\n"
            "- click_link(selector, text) — click buttons/links. Use valid "
            "Playwright selectors: CSS ('button', '.class', '#id') or text-based "
            "('text=Login', 'button:has-text(\"Sign In\")'). "
            "Optional 'text' param matches by visible text.\n"
            "- fill_form(fields, submit_selector) — fill and submit forms. "
            "fields is a JSON string like '{\"input[name=\\\"email\\\"]\": \"user@example.com\"}'\n"
            "- scroll_down(amount) / scroll_to_top() — scroll the page\n"
            "- compact_context(summary) — clear old screenshots/HTML to save tokens. "
            "ALWAYS call this after finding what you need and before interacting.\n"
            "- navigate(url) — go to a new URL (only if user asks)\n"
            "- clear_session() — clear cookies/session\n"
            "- write_report(issues) — write QA report CSV\n\n"
            "CRITICAL rules:\n"
            "1. Call compact_context(summary) after EVERY scan. Do NOT accumulate "
            "screenshots or large HTML dumps in context.\n"
            "2. Use valid Playwright selectors only. :contains() is jQuery, NOT valid.\n"
            "3. Be brief. Answer the user directly.\n"
            f"\nInitial issues: {json.dumps(issues, indent=2)}"
        )),
    ]

    _log("[main]", "entering interactive chat loop")
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            _log("[main]", "user exited chat")
            break

        if user_input.lower() == "done":
            _log("[main]", "user exited chat")
            break

        _log("[chat]", f"user said: {_trunc(user_input, 200)}")
        history.append(HumanMessage(content=user_input))

        for round_i in range(12):
            _log("[chat]", f"round {round_i + 1}: LLM thinking…")

            try:
                history = _auto_compact(history)
                response = chat_llm.invoke(history)
            except Exception as exc:
                err_msg = str(exc)
                _log("[chat]", f"LLM error: {err_msg}")
                if "400" in err_msg or "context" in err_msg.lower() or "token" in err_msg.lower():
                    _log("[chat]", "context overflow — force compacting and retrying")
                    history = _auto_compact(history, max_tokens=50_000)
                    try:
                        response = chat_llm.invoke(history)
                    except Exception as exc2:
                        _log("[chat]", f"LLM retry also failed: {exc2}")
                        print(f"\nAgent: Sorry, I hit a limit. The context is too large. "
                              "Try clearing the session or starting fresh.\n")
                        break
                else:
                    print(f"\nAgent: I encountered an error: {err_msg}\n")
                    break

            history.append(response)

            if not response.tool_calls:
                _log("[chat]", "LLM done — no tool calls")
                break

            tool_names = [tc["name"] for tc in response.tool_calls]
            _log("[chat]", f"LLM requested {len(response.tool_calls)} tool(s): {tool_names}")

            for tc in response.tool_calls:
                name = tc["name"]
                args = tc.get('args', {})
                _log("[chat]", f"  executing {name}…", args=_trunc(json.dumps(args, indent=2), 200))
                tool_fn = _tool_map.get(name)
                if not tool_fn:
                    result_str = f"Unknown tool: {name}"
                else:
                    try:
                        result_str = tool_fn.invoke(args)
                    except Exception as e:
                        result_str = f"Error: {e}"
                        _log("[chat]", f"  FAILED: {e}")
                result_str = str(result_str)
                if result_str.startswith("data:image/"):
                    kb = len(result_str) // 1024
                    _log("[chat]", f"  screenshot result: {kb}KB base64")
                else:
                    _log("[chat]", f"  result: {_trunc(result_str, 300)}")
                history.append(
                    ToolMessage(
                        content=result_str,
                        tool_call_id=tc["id"],
                        name=name,
                    )
                )

                if name == "compact_context":
                    summary = ""
                    content = str(result_str)
                    if "Preserved summary:" in content:
                        summary = content.split("Preserved summary:", 1)[1].strip()
                    sys_msg = None
                    for m in history:
                        if isinstance(m, SystemMessage):
                            sys_msg = m
                            break
                    old_count = len(history)
                    history = [sys_msg] if sys_msg else []
                    history.append(HumanMessage(
                        content=f"[Context compacted] {summary}"
                    ))
                    history.append(AIMessage(
                        content="Context compacted. Proceeding with the saved summary."
                    ))
                    _log("[chat]", f"compacted {old_count} -> {len(history)} messages")
                    break

        content = str(response.content) if hasattr(response, "content") else str(response)
        _log("[chat]", f"agent response: {_trunc(content, 500)}")

        if not content.strip():
            _log("[chat]", "empty response, retrying without tools")
            try:
                content = str(get_llm().invoke(history).content)
            except Exception:
                content = "I couldn't process that request. Please try again."

        print(f"\nAgent: {content}\n")


if __name__ == "__main__":
    main()
