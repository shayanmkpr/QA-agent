from langchain_core.tools import tool


@tool
def write_report(issues: str) -> str:
    """Write a QA test report.

    Accepts a JSON string containing a list of issues.
    Each issue must have: url, issue_type, description, category.
    The destination is determined by the active report repository (CSV or SQLite).
    """
    import json
    from infra.container import issue_reports

    try:
        data = json.loads(issues)
    except json.JSONDecodeError as e:
        return f"Error: invalid JSON — {e}"

    if not isinstance(data, list):
        return "Error: input must be a JSON array of issues"

    destination = issue_reports().write(data)
    return f"Report written to {destination} ({len(data)} issues)"   
