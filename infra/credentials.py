import json
from pathlib import Path
from typing import Optional


class CredentialStore:
    def __init__(self, path: str = ""):
        self._path = Path(path) if path else Path(__file__).resolve().parents[1] / "data" / "credentials.json"

    def _read(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _write(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get(self, key: str) -> Optional[dict]:
        return self._read().get(key)

    def set(self, key: str, data: dict) -> None:
        all_data = self._read()
        all_data[key] = data
        self._write(all_data)

    def delete(self, key: str) -> None:
        all_data = self._read()
        all_data.pop(key, None)
        self._write(all_data)

    def all(self) -> dict:
        return self._read()

    def keys(self) -> list:
        return list(self._read().keys())


_credential_store: Optional[CredentialStore] = None


def get_credential_store() -> CredentialStore:
    global _credential_store
    if _credential_store is None:
        _credential_store = CredentialStore()
    return _credential_store