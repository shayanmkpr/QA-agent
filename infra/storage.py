"""Storage abstraction for QA reference snapshots.

Currently persists to JSON files on disk. Swappable for a database later
without touching the app layer.
"""

import json
import hashlib
import datetime
from pathlib import Path
from typing import Optional


DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _url_to_filename(url: str) -> str:
    """Create a filesystem-safe filename from a URL using a short hash."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:32] + ".json"


def _ensure_dir() -> Path:
    """Return the data directory, creating it if necessary."""
    DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_DATA_DIR


def save_reference(url: str, html: str, screenshot: str) -> Path:
    """Save a reference snapshot for a URL.

    Args:
        url: Target page URL.
        html: Raw HTML content.
        screenshot: Base64-encoded PNG data URI string.

    Returns:
        Path to the saved JSON file.
    """
    data_dir = _ensure_dir()
    filepath = data_dir / _url_to_filename(url)
    payload = {
        "url": url,
        "html": html,
        "screenshot": screenshot,
        "saved_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    filepath.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return filepath


def load_reference(url: str) -> Optional[dict]:
    """Load the reference snapshot for a URL, if it exists.

    Returns None if no reference has been saved.
    """
    filepath = _ensure_dir() / _url_to_filename(url)
    if not filepath.exists():
        return None
    return json.loads(filepath.read_text(encoding="utf-8"))


def reference_exists(url: str) -> bool:
    """Return True if a reference snapshot exists for the given URL."""
    filepath = _ensure_dir() / _url_to_filename(url)
    return filepath.exists()
