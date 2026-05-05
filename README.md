# QA Agent

A LangGraph-based QA testing agent that captures reference snapshots of webpages, runs automated visual/deterministic checks, and reports issues.

## Usage

```bash
# Capture a reference snapshot
python main.py --set-reference --url https://example.com

# Run QA tests against a saved reference
python main.py --test --url https://example.com

# Interactive mode (follow-up questions with browser tools)
python main.py --url https://example.com
```

If no reference exists, the agent auto-runs set-reference. If one does, it prompts you to test.

## Agent Loop

```
         ┌─────────┐
         │  agent  │ ◀──────────────────────┐
         │ (think) │                        │
         └───┬─────┘                        │
             │                              │
      tool_calls?  ─── no ──▶ save_ref / analyze / END
             │                              │
            yes                             │
             ▼                              │
         ┌─────────┐                        │
         │  tools  │                        │
         │  (act)  │                        │
         └───┬─────┘                        │
             │                              │
    compact_context? ─── yes ──▶ ┌──────────┐
             │                    │ compact  │
             │                    │ (trim)   │
             │                    └────┬─────┘
             │                         │
             └────── no ───────────────┘
```

1. **Agent** calls LLM with system prompt + history. LLM decides next action (tool call or done).

2. **Tools** execute the call — navigate, scroll, screenshot, fetch HTML, click, fill form, etc.

3. **Scroll loop** — If the agent doesn't see what it needs in the current viewport, it calls `scroll_down(600)`, takes another screenshot, and checks again. Repeats until found or `at_bottom`.

4. **Compact** — Once the agent finds its target, it calls `compact_context(summary)`. This trims all previous screenshots and HTML dumps from context, keeping only the system prompt + summary, so token usage stays low.

5. **Act** — With clean context, the agent clicks the target, fills forms, or does whatever action is needed.

6. **Repeat or finish** — Back to step 1. When done, routes to save_reference (set-reference mode) or analyze → report (test mode).

## TODO

### Helpers and Utilities
- user profiles and credentials
- api tokens
- 

### Helpers and Utilities
- user profiles and credentials
- api tokens
- ! screenshot tool is not taking a complete screen shot, its just a cut off of the page that is rendered.

### Tools to add
- login and sign up.
- account balance setting. (or requesting for one)
- click on a link and compare with the corresponding reference.
- Hover for CSS animations

### Discovery
- How to load and check for animations
- How to build open claw
- How to track the agent's flow inside the browser?

### Claude Suggestions

1. **Test definition language** — Declarative YAML/JSON test scenarios with multi-step flows (navigate → fill → assert → screenshot), not just single-URL comparison.

2. **Assertion engine** — Text asserts, attribute asserts, existence/count asserts, network asserts (status codes), console error asserts. Runs deterministically, not via LLM.

3. **Visual regression (pixel-level)** — Pixelmatch or similar for precise diffing. LLM reserved for *classifying* diffs (real bug vs layout shift), not detecting them.

4. **Multi-scenario orchestration** — Run independent scenarios in sequence or parallel, each with its own session/reset. Suite-level pass/fail.

5. **Structured reporting** — HTML report with inline screenshots/diffs, JUnit XML for CI, summary stats (passed/failed/skipped, execution time, trends).

6. **Test data management** — Fixture system for form inputs, expected values, user roles. Per-environment configs (staging vs production).

7. **Browser robustness** — Wait strategies (element, network idle), iframe support, alert/prompt handling, file upload, hover/focus events, network interception, console error monitoring.

8. **Self-healing selectors** — Fallback selector strategies (text, parent structure, aria labels) when primary selector breaks.

9. **CI/CD integration** — Exit code reflects pass/fail, env var overrides for URLs/credentials, parallel execution, artifact output.

10. **Session & state management** — Multi-user scenarios, session isolation between scenarios, cookie/localStorage save/restore.
