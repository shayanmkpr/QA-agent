import base64
import io

import requests
from bs4 import BeautifulSoup
from langchain_core.tools import tool
from PIL import ImageGrab


@tool
def fetch_html(url: str) -> str:
    """Fetch and return the raw HTML content of a given URL."""
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.text


@tool
def fetch_content(url: str) -> str:
    """Fetch a URL and return its extracted readable text content (no HTML tags).

    Use this when you want to read the actual page content, not raw markup.
    """
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = (line.strip() for line in text.splitlines())
    return "\n".join(line for line in lines if line)


@tool
def screenshot() -> str:
    """Take a screenshot of the current screen and return it as a base64-encoded PNG data URI.

    Use this when you need to see what is currently visible on the user's screen.
    The returned string is a base64 data URI (data:image/png;base64,...) that can be
    rendered or passed to a vision-capable model.
    """
    try:
        img = ImageGrab.grab()
    except Exception as exc:
        return (
            f"[screenshot failed: {exc}]\n\n"
            "Hint: On macOS, grant the terminal app Screen Recording permission in "
            "System Settings > Privacy & Security > Screen Recording."
        )
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"
