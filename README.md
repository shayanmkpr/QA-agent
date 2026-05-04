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

## TODO

### Tools to add
- login and sign up.
- account balance setting. (or requesting for one)
- click on a link and compare with the corresponding reference.
- Hover for CSS animations

### Discovery
- How to load and check for animations
- How to build open claw
- How to track the agent's flow inside the browser?
