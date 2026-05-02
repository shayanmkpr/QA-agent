import base64
import io

from langchain_core.tools import tool
from PIL import ImageGrab


@tool
def screenshot() -> str:
    """Take a screenshot of the current screen and return it as a base64-encoded PNG data URI.

    Use this when you need to see what is currently visible on the user's screen.
    The returned string is a base64 data URI (data:image/png;base64,...) that can be
    rendered or passed to a vision-capable model.
    """
    try:
        img = ImageGrab.grab()
    except Exception as exc:  # FIXME: Catch specific PIL exceptions, not bare Exception.  # FIXME: Catch specific PIL exceptions, not bare Exception.
        return (
            f"[screenshot failed: {exc}]\n\n"
            "Hint: On macOS, grant the terminal app Screen Recording permission in "
            "System Settings > Privacy & Security > Screen Recording."
        )
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"
