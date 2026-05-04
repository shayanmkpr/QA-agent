import subprocess
from langchain_core.tools import tool


@tool
def ls(path: str = ".") -> str:
    """Run `ls -la` on the given path and return the output."""
    result = subprocess.run(["ls", "-la", path], capture_output=True, text=True)
    if result.returncode != 0:
        return f"Error: {result.stderr.strip()}"
    return result.stdout
