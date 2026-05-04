import argparse
import json
from infra.validate import validate_all
from infra import storage
from infra.config import get_llm
from infra.browser import get_browser_manager
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

    # Close browser so interactive mode gets a fresh connection
    try:
        get_browser_manager().close()
    except Exception:
        pass

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
            "\n\nYou also have a `write_report` tool. Use it when the user asks you to "
            "write or save the QA report. Pass a JSON array of issue objects, each with "
            "url, issue_type, description, and category."
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
                result_str = str(result_str)
                if result_str.startswith("data:image/"):
                    result_str = result_str[:75] + f" <{len(result_str) // 1024}KB base64 truncated>"
                elif len(result_str) > 2000:
                    result_str = result_str[:2000] + f"\n... [{len(result_str)} chars total, truncated]"
                history.append(
                    ToolMessage(content=result_str, tool_call_id=tc["id"], name=tc["name"])
                )

        print(f"\nAgent: {response.content}\n")
        if not str(response.content).strip():
            print("[debug] empty response, retrying without tools")
            response = get_llm().invoke(history)
            print(f"\nAgent: {response.content}\n")
        if not str(response.content).strip():
            print(f"[debug] still empty — response type={type(response).__name__} content_type={type(response.content).__name__} content_repr={repr(response.content)[:200]}")


if __name__ == "__main__":
    main()
