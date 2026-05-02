"""Tests for infra.storage"""

import pytest
from infra import storage


def test_save_and_load_reference(tmp_path, monkeypatch):
    """Roundtrip: save a reference then load it back."""
    monkeypatch.setattr(storage, "DEFAULT_DATA_DIR", tmp_path)

    url = "https://example.com"
    html = "<html><body>Hello</body></html>"
    screenshot = "data:image/png;base64,FAKE"

    path = storage.save_reference(url, html, screenshot)
    assert path.exists()

    assert storage.reference_exists(url)

    ref = storage.load_reference(url)
    assert ref is not None
    assert ref["url"] == url
    assert ref["html"] == html
    assert ref["screenshot"] == screenshot
    assert "saved_at" in ref


def test_load_missing_reference(tmp_path, monkeypatch):
    """Loading a non-existent reference returns None."""
    monkeypatch.setattr(storage, "DEFAULT_DATA_DIR", tmp_path)
    assert storage.load_reference("https://missing.com") is None


def test_reference_exists_false(tmp_path, monkeypatch):
    """reference_exists returns False when nothing has been saved."""
    monkeypatch.setattr(storage, "DEFAULT_DATA_DIR", tmp_path)
    assert storage.reference_exists("https://missing.com") is False
