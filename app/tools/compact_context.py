"""Context compaction tool — lets the agent slim down conversation history
once it has found what it needs, keeping only essential context plus a
memory of the previous thought process."""

from langchain_core.tools import tool


@tool
def compact_context(summary: str) -> str:
    """Compact the conversation context to save tokens.

    Call this AFTER you have found something important (e.g., after scrolling
    to the right section, taking a screenshot, and identifying what the user
    needs). This removes old screenshots and verbose HTML/tool outputs from
    the context while preserving your findings.

    Args:
        summary: A concise summary of what you've discovered so far, what page
                 you're on, and what your next steps are.
                 Example: "Logged into dashboard at /dashboard. Found user table
                 with 3 columns. Next: check the settings page."

    The summary you provide will be preserved as context memory so you don't
    lose track of your progress.
    """
    # The actual trimming happens in the graph (compact_node).
    # This tool just signals the intent and carries the summary.
    return (
        f"[compact_context] Context will be compacted.\n"
        f"Preserved summary: {summary}"
    )
