import argparse
import json
from infra.validate import validate_all
from infra import storage
from infra.config import get_llm
from app.graph import graph, tools
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage


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

    # 1. Check for existing reference
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

    # 2. Run the graph
    result = graph.invoke({"url": url, "mode": mode, "messages": []})

    if mode == "set_reference":
        print("Reference saved.")
        return

    # 3. Print short summary
    issues = result.get("issues", [])
    print(f"Test complete — {len(issues)} issue(s) found.")

    # 4. Chat loop with tool access
    print()
    print("You can now ask follow-up questions. Type 'done' to exit.")
    print()

    tool_map = {t.name: t for t in tools}
    chat_llm = get_llm().bind_tools(tools)

    history = [
        SystemMessage(content=(
            f"You are a QA assistant helping investigate the page {url}. "
            f"The automated test found {len(issues)} issues. "
            "You have browser tools available — use them to inspect the page, "
            "take screenshots, fetch HTML, or fetch rendered text content. "
            "Help the user understand what's happening."
            f"\n\nInitial issues: {json.dumps(issues, indent=2)}"
        )),
    ]

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() == "done":
            break

        history.append(HumanMessage(content=user_input))

        for _ in range(10):
            response = chat_llm.invoke(history)
            history.append(response)

            if not response.tool_calls:
                break

            for tc in response.tool_calls:
                tool_fn = tool_map.get(tc["name"])
                if not tool_fn:
                    result_str = f"Unknown tool: {tc['name']}"
                else:
                    try:
                        result_str = tool_fn.invoke(tc["args"])
                    except Exception as e:
                        result_str = f"Error: {e}"
                history.append(
                    ToolMessage(content=str(result_str), tool_call_id=tc["id"], name=tc["name"])
                )

        print(f"\nAgent: {response.content}\n")


if __name__ == "__main__":
    main()
