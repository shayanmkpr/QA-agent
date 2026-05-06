"""Prompt templates for the QA agent.

Every prompt the agent uses lives here as a pure function.  No prompt text
is hardcoded in consumer modules (main, runner, graph, etc.).

Template functions take keyword parameters so callers are explicit about
what they inject.
"""

import json


# ---------------------------------------------------------------------------
# Shared building blocks
# ---------------------------------------------------------------------------

_SELECTOR_GUIDELINES = (
    "Valid Playwright selectors for click_link, hover, and fill_form:\n"
    "- CSS:   'button', '.class-name', '#element-id', 'a[href=\"/login\"]'\n"
    "- Text:  'text=Login', 'button:has-text(\"Sign In\")'\n"
    "- ARIA:  '[aria-label=\"Menu\"]'\n"
    "- NEVER use jQuery selectors like :contains() — they are NOT supported."
)

_COMPACT_GUIDELINES = (
    "After scanning a page (fetch_content / webpage_screenshot / fetch_html), "
    "call compact_context(summary) to keep the context window lean. "
    "Never keep multiple screenshots or HTML dumps in context."
)

_CREDENTIALS_BLOCK = (
    "Credentials are available.  When a page requires authentication:\n"
    "1. Look for a Login / Sign In link or button and click it.\n"
    "2. Use fill_form() with the credential fields below.\n"
    "3. Submit the form.\n"
    "4. Verify you reach an authenticated page (dashboard, account, etc.)."
)

_SCENARIO_TOOLS = (
    "## Available tools\n"
    "- navigate(url) — go to a URL\n"
    "- click_link(selector, text) — click elements\n"
    "- hover(selector) — hover to reveal hidden UI\n"
    "- fill_form(fields, submit_selector) — fill and submit forms\n"
    "- fetch_html() — raw page HTML\n"
    "- fetch_content() — visible page text\n"
    "- webpage_screenshot() — full-page screenshot (base64 PNG)\n"
    "- scroll_down(amount) / scroll_to_top() — scroll the viewport\n"
    "- check_console_errors() — JS errors and warnings\n"
    "- check_network() — failed / slow HTTP requests\n"
    "- compact_context(summary) — trim old context to save tokens\n"
    "- clear_session() — clear cookies and storage"
)


# ---------------------------------------------------------------------------
# Main QA agent (REPL)
# ---------------------------------------------------------------------------

def qa_agent_system(credentials_display: str) -> str:
    """System prompt for the interactive REPL agent."""
    return (
        "You are a QA testing assistant.  You have access to a headless "
        "Chromium browser and can navigate, click, fill forms, hover, scroll, "
        "take screenshots, inspect HTML, check console errors and network "
        "issues, and run predefined test scenarios.\n\n"
        f"Available credentials: {credentials_display}\n\n"
        "Guidelines:\n"
        "- Be concise and direct.\n"
        f"- {_COMPACT_GUIDELINES}\n"
        f"- {_SELECTOR_GUIDELINES}\n"
        "- click_link(selector) or click_link(selector, text) to click buttons or links.\n"
        "- hover(selector) to reveal tooltips, dropdowns, or hover-only UI.\n"
        "- fill_form(fields_json, submit_selector) to fill and submit forms.\n"
        "- check_console_errors() after page interactions to catch JS errors.\n"
        "- check_network() after navigation to catch broken requests or slow APIs.\n"
        "- run_scenarios(scenarios_file, url) to execute predefined scenarios.\n"
        "- The browser keeps state between commands — sessions persist."
    )


# ---------------------------------------------------------------------------
# Login setup
# ---------------------------------------------------------------------------

def login_setup(base_url: str, credentials_json: str) -> str:
    """Prompt for the scenario runner's pre-login step."""
    return (
        f"You are a QA assistant.  Log in to {base_url}.\n\n"
        "Steps:\n"
        "1. Navigate to the site and locate a Login / Sign In link; click it.\n"
        "2. Fill the login form with the credentials below.\n"
        "3. Submit the form.\n"
        "4. Confirm you reach an authenticated page (dashboard, account, profile, etc.).\n"
        "5. Dismiss any banner or modal that appears after login.\n"
        "6. Call compact_context('Logged in successfully'), then stop.\n\n"
        f"Credentials: {credentials_json}\n\n"
        "If no login link is visible, try /login, /signin, or /auth.\n"
        "If login fails after reasonable attempts, report what happened."
    )


# ---------------------------------------------------------------------------
# Scenario execution
# ---------------------------------------------------------------------------

def scenario_execution(
    scenario_id: str,
    scenario_title: str,
    section: str,
    base_url: str,
    steps: list[str],
    expected: list[str],
    credentials: dict,
    requires_auth: bool,
    is_auth_scenario: bool,
) -> str:
    """Prompt that the LLM receives before each scenario run."""
    parts = [
        f"You are a QA test agent executing Scenario {scenario_id}: {scenario_title}.",
        f"Section: {section}.",
        f"The application is at: {base_url}",
        "",
    ]

    if steps:
        parts.append("## Steps to execute:")
        for i, step in enumerate(steps, 1):
            parts.append(f"{i}. {step}")
        parts.append("")

    if expected:
        parts.append("## Expected outcomes:")
        for i, exp in enumerate(expected, 1):
            parts.append(f"{i}. {exp}")
        parts.append("")

    if credentials and (requires_auth or is_auth_scenario):
        parts.append("## Credentials")
        parts.append(f"Use these for login: {json.dumps(credentials)}")
        if is_auth_scenario:
            parts.append("Start with a CLEAN session — call clear_session() first.")
            parts.append(
                "Test BOTH valid and invalid paths.  When a step says 'invalid', "
                "a failure/error is the EXPECTED result — mark it PASS if the "
                "app correctly rejects the input."
            )
        parts.append("")

    parts.append(_SCENARIO_TOOLS)
    parts.append("")

    parts.append("## CRITICAL rules")
    parts.append("1. Navigate to the starting page first, then proceed step by step.")
    parts.append("2. Call compact_context(summary) after EVERY scan to save tokens.")
    parts.append("3. Use only valid Playwright selectors.  :contains() is jQuery — NOT valid.")
    parts.append("4. If an element is not found, try 2-3 alternative selectors before reporting.")
    parts.append("5. After executing ALL steps, provide your VERDICT:")
    parts.append("   - State VERDICT: PASS if all expected outcomes are met.")
    parts.append("   - State VERDICT: FAIL if any expected outcome is not met, with details.")
    parts.append("   - Include specific evidence from screenshots or page content.")
    parts.append("6. Do NOT call write_report() — reporting is handled automatically.")
    parts.append("7. If a scenario tests error/validation, a correct error message = PASS.")

    return "\n".join(parts)
