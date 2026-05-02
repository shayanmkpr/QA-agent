import argparse
from infra.validate import validate_all
from app.graph import graph


def main():
    validate_all()

    parser = argparse.ArgumentParser(description="QA Tester Agent")
    parser.add_argument(
        "--set-reference",
        action="store_true",
        help="Capture and save a reference snapshot",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run QA test against saved reference",
    )
    parser.add_argument("--url", type=str, help="Target URL")
    args = parser.parse_args()

    url = args.url or input("URL: ").strip()

    if args.set_reference:
        mode = "set_reference"
    elif args.test:
        mode = "test"
    else:
        mode = input("Mode (set_reference / test): ").strip()

    # Kick off the graph with an empty message list so the agent node
    # initialises the conversation.
    result = graph.invoke({"url": url, "mode": mode, "messages": []})

    if mode == "set_reference":
        print(f"Reference saved. Snapshot: {result.get('screenshot', 'N/A')[:50]}...")
        print(f"HTML length: {len(result.get('html', ''))}")
    else:
        report_path = result.get("report_path", "qa_report.csv")
        print(f"Report written to: {report_path}")
        print(f"Total issues found: {len(result.get('issues', []))}")


if __name__ == "__main__":
    main()
