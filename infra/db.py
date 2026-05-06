"""Lightweight SQLite wrapper for persisting prompts, reports, and config data.

Creates ``data/qa_agent.db`` automatically on first access.  Uses the same
singleton pattern as the rest of the ``infra`` layer.
"""

import sqlite3
from pathlib import Path
from typing import Any, Optional

DEFAULT_DB_PATH = Path("data/qa_agent.db")


class Database:
    """Thread-safe wrapper around a single SQLite database file.

    Usage::

        db = get_db()
        db.set_prompt("system", "You are a QA agent...")
        row = db.get_prompt("system")

    Tables are created automatically on first open.
    """

    def __init__(self, path: Path = DEFAULT_DB_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    # -- schema ---------------------------------------------------------------

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS prompts (
                key         TEXT PRIMARY KEY,
                template    TEXT NOT NULL,
                description TEXT DEFAULT '',
                updated_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS qa_reports (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                url              TEXT    NOT NULL,
                scenario_id      TEXT    DEFAULT '',
                status           TEXT    NOT NULL,
                findings         TEXT    DEFAULT '',
                duration_seconds REAL    DEFAULT 0,
                created_at       TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS credentials (
                name       TEXT PRIMARY KEY,
                data       TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS session_state (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        self._conn.commit()

    # -- raw SQL helpers ------------------------------------------------------

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self._conn.execute(sql, params)

    def fetch_all(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return self._conn.execute(sql, params).fetchall()

    def fetch_one(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        return self._conn.execute(sql, params).fetchone()

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # -- prompts table --------------------------------------------------------

    def get_prompt(self, key: str, default: str = "") -> str:
        """Return a stored prompt template, or *default* if not found."""
        row = self.fetch_one("SELECT template FROM prompts WHERE key = ?", (key,))
        return row["template"] if row else default

    def set_prompt(self, key: str, template: str, description: str = "") -> None:
        """Store (or overwrite) a prompt template by key."""
        self.execute(
            "INSERT OR REPLACE INTO prompts (key, template, description, updated_at) "
            "VALUES (?, ?, ?, datetime('now'))",
            (key, template, description),
        )
        self.commit()

    def list_prompts(self) -> list[sqlite3.Row]:
        """Return all stored prompt keys and descriptions."""
        return self.fetch_all("SELECT key, description FROM prompts ORDER BY key")

    # -- reports table --------------------------------------------------------

    def save_report(
        self,
        url: str,
        status: str,
        scenario_id: str = "",
        findings: str = "",
        duration: float = 0.0,
    ) -> int:
        """Insert a QA report row.  Returns the new row ID."""
        cur = self.execute(
            "INSERT INTO qa_reports (url, scenario_id, status, findings, duration_seconds) "
            "VALUES (?, ?, ?, ?, ?)",
            (url, scenario_id, status, findings, duration),
        )
        self.commit()
        return cur.lastrowid

    def get_reports(self, limit: int = 50) -> list[sqlite3.Row]:
        return self.fetch_all(
            "SELECT * FROM qa_reports ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )

    # -- credentials table ----------------------------------------------------

    def get_credential(self, name: str) -> Optional[dict]:
        row = self.fetch_one("SELECT data FROM credentials WHERE name = ?", (name,))
        if not row:
            return None
        import json
        return json.loads(row["data"])

    def set_credential(self, name: str, data: dict) -> None:
        import json
        self.execute(
            "INSERT OR REPLACE INTO credentials (name, data) VALUES (?, ?)",
            (name, json.dumps(data)),
        )
        self.commit()

    def list_credentials(self) -> dict[str, dict]:
        import json
        rows = self.fetch_all("SELECT name, data FROM credentials")
        return {r["name"]: json.loads(r["data"]) for r in rows}

    # -- session state (key-value) ---------------------------------------------

    def get_state(self, key: str, default: str = "") -> str:
        row = self.fetch_one("SELECT value FROM session_state WHERE key = ?", (key,))
        return row["value"] if row else default

    def set_state(self, key: str, value: str) -> None:
        self.execute(
            "INSERT OR REPLACE INTO session_state (key, value) VALUES (?, ?)",
            (key, value),
        )
        self.commit()


# -- singleton ----------------------------------------------------------------

_db: Optional[Database] = None


def get_db(path: Optional[Path] = None) -> Database:
    """Return (or create) the shared Database singleton."""
    global _db
    if _db is None:
        _db = Database(path or DEFAULT_DB_PATH)
    return _db
