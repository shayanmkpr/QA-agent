import csv
import json
import time
import re
from pathlib import Path
from typing import Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from app.scenarios.models import Scenario, ScenarioResult
from app.scenarios.parser import parse_scenarios
from app.scenarios.prompts import build_scenario_prompt
from prompts.templates import login_setup
from app.tools import (
    navigate,
    click_link,
    fetch_content,
    fetch_html,
    fill_form,
    webpage_screenshot,
    clear_session,
    scroll_down,
    scroll_to_top,
    compact_context,
)
from infra.browser import get_browser_manager
from infra.config import PROVIDER, _registry
from infra.credentials import get_credential_store
from infra.logging import _log, _trunc

REPORT_FILE = "qa_scenarios_report.csv"

_SCENARIO_TOOLS = [
    navigate,
    click_link,
    fill_form,
    fetch_html,
    fetch_content,
    webpage_screenshot,
    scroll_down,
    scroll_to_top,
    compact_context,
    clear_session,
]
_SCENARIO_TOOL_MAP = {t.name: t for t in _SCENARIO_TOOLS}
_MAX_ROUNDS_PER_SCENARIO = 25
_MAX_LOGIN_SETUP_ROUNDS = 12


def _get_scenario_llm():
    """Get an LLM instance for scenario execution.

    Uses the same provider from infra.config but always uses tool_choice='auto'
    so the LLM can stop and give a verdict without being forced to call tools.
    """
    factory = _registry[PROVIDER]
    base_llm = factory()
    # Recreate with explicit tool_choice='auto' to prevent env TOOL_CHOICE='any'
    # from forcing hallucinated tool calls when the LLM should deliver a verdict
    return ChatOpenAI(
        model=base_llm.model_name,
        temperature=0,
        base_url=base_llm.openai_api_base if hasattr(base_llm, 'openai_api_base') else None,
        api_key=base_llm.openai_api_key if hasattr(base_llm, 'openai_api_key') else None,
        model_kwargs={"tool_choice": "auto"},
    )


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

    _log("[scenario-compact]", f"context at ~{estimated} tokens, compacting")

    sys_idx = None
    for i, msg in enumerate(history):
        if isinstance(msg, SystemMessage):
            sys_idx = i
            break

    recent = []
    screenshot_found = False
    for msg in reversed(history):
        content = str(msg.content) if hasattr(msg, "content") else ""
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
        "Previous scan results cleared. The page is still loaded in the browser. "
        "Use webpage_screenshot() or fetch_content() to see the current state."
    ))
    compacted.append(AIMessage(content="Understood."))
    compacted.extend(recent)

    _log("[scenario-compact]", f"{len(history)} -> {len(compacted)} messages")
    return compacted


def _run_scenario_llm(
    scenario: Scenario,
    credentials: dict,
    base_url: str,
) -> ScenarioResult:
    """Execute a single scenario via LLM agent + tools loop."""
    llm = _get_scenario_llm().bind_tools(_SCENARIO_TOOLS)
    system_prompt = build_scenario_prompt(scenario, credentials, base_url)
    history: list = [SystemMessage(content=system_prompt)]
    history.append(HumanMessage(
        content=f"Begin Scenario {scenario.id}: {scenario.title}. "
        f"Navigate to {base_url} and execute the steps."
    ))

    start_time = time.time()
    steps_attempted = 0

    for round_i in range(_MAX_ROUNDS_PER_SCENARIO):
        _log("[scenario]", f"  scenario {scenario.id} round {round_i + 1}/{_MAX_ROUNDS_PER_SCENARIO}")

        try:
            history = _auto_compact(history)
            response = llm.invoke(history)
        except Exception as exc:
            err_msg = str(exc)
            _log("[scenario]", f"  LLM error: {err_msg}")
            if "400" in err_msg or "context" in err_msg.lower() or "token" in err_msg.lower():
                history = _auto_compact(history, max_tokens=50_000)
                try:
                    response = llm.invoke(history)
                except Exception as exc2:
                    return ScenarioResult(
                        scenario_id=scenario.id,
                        section=scenario.section,
                        title=scenario.title,
                        status="ERROR",
                        findings="LLM context overflow, unable to recover",
                        duration_seconds=time.time() - start_time,
                        steps_attempted=steps_attempted,
                        error_message=str(exc2),
                    )
            else:
                return ScenarioResult(
                    scenario_id=scenario.id,
                    section=scenario.section,
                    title=scenario.title,
                    status="ERROR",
                    findings=f"LLM error: {err_msg[:500]}",
                    duration_seconds=time.time() - start_time,
                    steps_attempted=steps_attempted,
                    error_message=err_msg,
                )

        history.append(response)

        if not response.tool_calls:
            content = str(response.content) if hasattr(response, "content") else ""
            _log("[scenario]", f"  done — no tool calls, extracting verdict")
            return _extract_verdict(scenario, content, start_time, steps_attempted)

        steps_attempted += len(response.tool_calls)
        tool_names = [tc["name"] for tc in response.tool_calls]
        _log("[scenario]", f"  tools ({len(response.tool_calls)}): {tool_names}")

        for tc in response.tool_calls:
            name = tc["name"]
            args = tc.get("args", {})
            _log("[scenario]", f"    {name}: {_trunc(json.dumps(args), 200)}")

            tool_fn = _SCENARIO_TOOL_MAP.get(name)
            if not tool_fn:
                result_str = f"Unknown tool: {name}"
            else:
                try:
                    result_str = tool_fn.invoke(args)
                except Exception as e:
                    result_str = f"Error executing {name}: {e}"
                    _log("[scenario]", f"    FAILED: {e}")

            result_str = str(result_str)
            if result_str.startswith("data:image/"):
                _log("[scenario]", f"    screenshot: {len(result_str) // 1024}KB")
            else:
                _log("[scenario]", f"    result: {_trunc(result_str, 200)}")

            history.append(ToolMessage(
                content=result_str,
                tool_call_id=tc["id"],
                name=name,
            ))

            if name == "compact_context":
                summary = ""
                if "Preserved summary:" in result_str:
                    summary = result_str.split("Preserved summary:", 1)[1].strip()
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
                _log("[scenario]", f"    compacted {old_count} -> {len(history)} messages")
                break

    return ScenarioResult(
        scenario_id=scenario.id,
        section=scenario.section,
        title=scenario.title,
        status="ERROR",
        findings=f"Max rounds ({_MAX_ROUNDS_PER_SCENARIO}) reached without verdict",
        duration_seconds=time.time() - start_time,
        steps_attempted=steps_attempted,
        error_message="Max rounds exceeded",
    )


def _extract_verdict(
    scenario: Scenario,
    content: str,
    start_time: float,
    steps_attempted: int,
) -> ScenarioResult:
    """Parse the LLM's final response to extract PASS/FAIL verdict."""
    content_upper = content.upper()

    if "VERDICT: PASS" in content_upper:
        status = "PASS"
    elif "VERDICT: FAIL" in content_upper:
        status = "FAIL"
    elif "VERDICT:" in content_upper:
        # Has a verdict marker but unclear - look for pass indicators
        if "PASS" in content_upper.split("VERDICT:")[1][:50]:
            status = "PASS"
        else:
            status = "FAIL"
    else:
        status = "FAIL"

    findings = content[:2000] if content else "No findings provided"

    return ScenarioResult(
        scenario_id=scenario.id,
        section=scenario.section,
        title=scenario.title,
        status=status,
        findings=findings,
        duration_seconds=time.time() - start_time,
        steps_attempted=steps_attempted,
    )


def _run_login_setup(credentials: dict, base_url: str) -> Optional[str]:
    """Navigate to login page and log in using credentials.

    Returns None on success, or an error message on failure.
    """
    _log("[scenario]", "  running login setup...")
    get_browser_manager().clear_context()

    restricted_tools = [
        navigate, click_link, fill_form, fetch_content,
        webpage_screenshot, compact_context, clear_session,
    ]
    restricted_map = {t.name: t for t in restricted_tools}
    llm = _get_scenario_llm().bind_tools(restricted_tools)

    creds_json = json.dumps(credentials)
    prompt = login_setup(base_url=base_url, credentials_json=creds_json)

    history: list = [SystemMessage(content=prompt)]

    for round_i in range(_MAX_LOGIN_SETUP_ROUNDS):
        _log("[scenario]", f"    login round {round_i + 1}")
        try:
            response = llm.invoke(history)
        except Exception as exc:
            return f"Login setup LLM error: {exc}"

        history.append(response)

        if not response.tool_calls:
            _log("[scenario]", "  login setup complete")
            return None

        for tc in response.tool_calls:
            name = tc["name"]
            args = tc.get("args", {})
            tool_fn = restricted_map.get(name)
            if not tool_fn:
                result = f"Unknown tool: {name}"
            else:
                try:
                    result = str(tool_fn.invoke(args))
                except Exception as e:
                    result = f"Error: {e}"

            history.append(ToolMessage(
                content=result,
                tool_call_id=tc["id"],
                name=name,
            ))

            if name == "compact_context":
                summary = ""
                if "Preserved summary:" in result:
                    summary = result.split("Preserved summary:", 1)[1].strip()
                sys_msg = next(
                    (m for m in history if isinstance(m, SystemMessage)), None
                )
                history = [sys_msg] if sys_msg else []
                history.append(HumanMessage(
                    content=f"[Context compacted] {summary}"
                ))
                history.append(AIMessage(content="Proceeding."))
                break

    return "Login setup did not complete within max rounds"


def run_all_scenarios(
    scenarios: list[Scenario],
    credentials: dict,
    base_url: str,
) -> list[ScenarioResult]:
    """Run all scenarios sequentially and return results."""
    results: list[ScenarioResult] = []
    total = len(scenarios)

    for i, scenario in enumerate(scenarios):
        _log("[scenario]", f"\n{'=' * 60}")
        _log("[scenario]", f"[{i + 1}/{total}] Scenario {scenario.id}: {scenario.title}")
        _log("[scenario]", f"  Section: {scenario.section}")
        _log("[scenario]", f"  is_auth_scenario={scenario.is_auth_scenario} requires_auth={scenario.requires_auth}")

        if scenario.is_auth_scenario:
            get_browser_manager().clear_context()
        elif scenario.requires_auth:
            err = _run_login_setup(credentials, base_url)
            if err:
                _log("[scenario]", f"  LOGIN FAILED: {err}")
                results.append(ScenarioResult(
                    scenario_id=scenario.id,
                    section=scenario.section,
                    title=scenario.title,
                    status="ERROR",
                    findings="Login setup failed",
                    error_message=err,
                ))
                continue

        result = _run_scenario_llm(scenario, credentials, base_url)
        results.append(result)
        _log("[scenario]", f"  => {result.status} ({result.duration_seconds:.1f}s)")

        # Pause between scenarios for stability
        time.sleep(1)

    return results


def write_scenario_report(results: list[ScenarioResult]) -> str:
    """Write scenario results to a CSV report file. Returns the file path."""
    filepath = Path(REPORT_FILE)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Scenario ID", "Section", "Title", "Status",
            "Duration (s)", "Steps", "Findings", "Error"
        ])
        for r in results:
            writer.writerow([
                r.scenario_id,
                r.section,
                r.title,
                r.status,
                round(r.duration_seconds, 1),
                r.steps_attempted,
                r.findings[:500],
                r.error_message,
            ])
    return str(filepath)


def print_summary(results: list[ScenarioResult]) -> None:
    """Print a summary of the scenario run results."""
    pass_count = sum(1 for r in results if r.status == "PASS")
    fail_count = sum(1 for r in results if r.status == "FAIL")
    error_count = sum(1 for r in results if r.status == "ERROR")
    skip_count = sum(1 for r in results if r.status == "SKIP")
    total_time = sum(r.duration_seconds for r in results)

    print()
    print("=" * 60)
    print("  SCENARIO RUN COMPLETE")
    print("=" * 60)
    print(f"  Total:    {len(results)}")
    print(f"  Pass:     {pass_count}")
    print(f"  Fail:     {fail_count}")
    print(f"  Error:    {error_count}")
    print(f"  Skip:     {skip_count}")
    print(f"  Duration: {total_time:.0f}s ({total_time / 60:.1f}m)")
    print(f"  Report:   {REPORT_FILE}")
    print("=" * 60)

    if fail_count > 0:
        print("\nFailed scenarios:")
        for r in results:
            if r.status == "FAIL":
                print(f"  [{r.scenario_id}] {r.title} ({r.section})")

    if error_count > 0:
        print("\nErrored scenarios:")
        for r in results:
            if r.status == "ERROR":
                print(f"  [{r.scenario_id}] {r.title} — {r.error_message[:120]}")
    print()
