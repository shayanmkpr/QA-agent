import json
from app.scenarios.models import Scenario


def build_scenario_prompt(scenario: Scenario, credentials: dict, base_url: str) -> str:
    parts = [
        f"You are a QA test agent executing Scenario {scenario.id}: {scenario.title}.",
        f"Section: {scenario.section}.",
        f"The application is at: {base_url}",
        "",
    ]

    if scenario.steps:
        parts.append("## Steps to execute:")
        for i, step in enumerate(scenario.steps, 1):
            parts.append(f"{i}. {step}")
        parts.append("")

    if scenario.expected:
        parts.append("## Expected outcomes:")
        for i, exp in enumerate(scenario.expected, 1):
            parts.append(f"{i}. {exp}")
        parts.append("")

    if credentials and (scenario.requires_auth or scenario.is_auth_scenario):
        parts.append("## Credentials")
        parts.append(f"Use these for login: {json.dumps(credentials)}")
        if scenario.is_auth_scenario:
            parts.append("Start with a CLEAN session (call clear_session() first).")
            parts.append(
                "Test BOTH valid and invalid paths. When a step says 'invalid', "
                "a failure/error is the EXPECTED result — mark it PASS if the app "
                "correctly rejects the input."
            )
        parts.append("")

    parts.append("## Available tools")
    parts.append("- navigate(url) — go to a URL")
    parts.append("- click_link(selector, text) — click elements. Valid selectors: CSS, text=, :has-text()")
    parts.append("- fill_form(fields, submit_selector) — fill form fields. fields is JSON mapping selectors -> values")
    parts.append("- fetch_html() — get raw page HTML")
    parts.append("- fetch_content() — get visible text content")
    parts.append("- webpage_screenshot() — take full-page screenshot (base64 PNG)")
    parts.append("- scroll_down(amount) / scroll_to_top() — scroll the page")
    parts.append("- compact_context(summary) — clear old screenshots/HTML to save tokens")
    parts.append("- clear_session() — clear cookies/storage, fresh browser state")
    parts.append("")

    parts.append("## CRITICAL rules")
    parts.append("1. Navigate to the starting page first, then proceed step by step.")
    parts.append("2. Call compact_context(summary) after EVERY scan to save tokens.")
    parts.append("3. Use only valid Playwright selectors. :contains() is jQuery — NOT valid.")
    parts.append("4. If an element is not found, try 2-3 alternative selectors before reporting.")
    parts.append("5. After executing ALL steps, provide your VERDICT:")
    parts.append("   - State VERDICT: PASS if all expected outcomes are met.")
    parts.append("   - State VERDICT: FAIL if any expected outcome is not met, with details.")
    parts.append("   - Include specific evidence from screenshots or page content.")
    parts.append("6. Do NOT call write_report() — reporting is handled automatically.")
    parts.append("7. If a scenario tests error/validation behavior, a correct error message = PASS.")

    return "\n".join(parts)
