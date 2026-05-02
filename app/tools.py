import base64
import io

from langchain_core.tools import tool
from PIL import ImageGrab

from infra.browser import get_browser_manager


@tool
def fetch_html(url: str) -> str:
    """Fetch and return the raw HTML content of a given URL using a headless browser."""
    return get_browser_manager().get_html(url)


@tool
def fetch_content(url: str) -> str:
    """Fetch a URL and return its extracted readable text content (no HTML tags).

    Use this when you want to read the actual page content, not raw markup.
    """
    return get_browser_manager().get_text(url)


@tool
def webpage_screenshot(url: str) -> str:
    """Open a URL in a headless browser and return a full-page screenshot as a base64-encoded PNG data URI.

    Use this when you need a complete screenshot of a specific webpage.
    The returned format matches the screen screenshot tool (data:image/png;base64,...)
    so it can be consumed by vision-capable models the same way.
    """
    return get_browser_manager().screenshot(url)


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
