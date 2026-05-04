import csv
from pathlib import Path
from langchain_core.tools import tool


@tool
def write_report(issues: str) -> str:
    """Write a QA test report to `qa_report.csv`.

    Accepts a JSON string containing a list of issues.
    Each issue must have: url, issue_type, description, category.
    """
    import json

    try:
        data = json.loads(issues)
    except json.JSONDecodeError as e:
        return f"Error: invalid JSON — {e}"

    if not isinstance(data, list):
        return "Error: input must be a JSON array of issues"

    report_path = Path("qa_report.csv")
    with open(report_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["URL", "Issue Type", "Description", "Category"])
        for issue in data:
            writer.writerow([
                issue.get("url", ""),
                issue.get("issue_type", ""),
                issue.get("description", ""),
                issue.get("category", ""),
            ])

    return f"Report written to {report_path} ({len(data)} issues)"
