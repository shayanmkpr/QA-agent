"""Service definitions for the QA agent.

Runtime services (browser, credentials, reports, snapshots).  Choose the
implementation here by editing the _SINGLE COMMENTED LINE at the bottom of
this file.  Higher-level code just imports from here — it never constructs
a dependency itself."""

from __future__ import annotations

import csv
import json
import sqlite3
from abc import abstractmethod
from pathlib import Path
from typing import Any, Optional, Protocol

# Internal references — set once at module load.
_credentials: "CredentialRepository"
_issue_reports: "IssueReportWriter"
_scenario_reports: "ScenarioReportWriter"
_snapshots: "SnapshotRepository"

# ==========================================================================
# Protocols — what a service must do, not how it does it
# ==========================================================================

class CredentialRepository(Protocol):
    """Store and retrieve named credential dictionaries."""

    @abstractmethod
    def get(self, key: str) -> Optional[dict]: ...
    @abstractmethod
    def set(self, key: str, data: dict) -> None: ...
    @abstractmethod
    def delete(self, key: str) -> None: ...
    @abstractmethod
    def all(self) -> dict: ...
    @abstractmethod
    def keys(self) -> list: ...


class IssueReportWriter(Protocol):
    @abstractmethod
    def write(self, issues: list[dict]) -> str: ...


class ScenarioReportWriter(Protocol):
    @abstractmethod
    def write(self, results: list) -> str: ...


class SnapshotRepository(Protocol):
    @abstractmethod
    def save(self, url: str, html: str, screenshot: str) -> str: ...
    @abstractmethod
    def load(self, url: str) -> Optional[dict]: ...
    @abstractmethod
    def exists(self, url: str) -> bool: ...


# ==========================================================================
# Implementations — swap these in/out by editing the factory below
# ==========================================================================

# -- credentials -----------------------------------------------------------

class JsonCredentialRepository:
    def __init__(self, path: str = "data/credentials.json"):
        from infra.credentials import CredentialStore
        self._store = CredentialStore(path)
    def get(self, key: str) -> Optional[dict]: return self._store.get(key)
    def set(self, key: str, data: dict) -> None: self._store.set(key, data)
    def delete(self, key: str) -> None: self._store.delete(key)
    def all(self) -> dict: return self._store.all()
    def keys(self) -> list: return self._store.keys()


class SqliteCredentialRepository:
    def __init__(self, db):
        self._db = db
    def get(self, key: str) -> Optional[dict]: return self._db.get_credential(key)
    def set(self, key: str, data: dict) -> None: self._db.set_credential(key, data)
    def delete(self, key: str) -> None:
        self._db.execute("DELETE FROM credentials WHERE name = ?", (key,))
        self._db.commit()
    def all(self) -> dict: return self._db.list_credentials()
    def keys(self) -> list: return list(self._db.list_credentials().keys())


# -- issue reports ---------------------------------------------------------

class CsvIssueReportWriter:
    def __init__(self, path: str = "qa_report.csv"):
        self._path = Path(path)
    def write(self, issues: list[dict]) -> str:
        with open(self._path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["URL", "Issue Type", "Description", "Category"])
            for issue in issues:
                writer.writerow([
                    issue.get("url", ""),
                    issue.get("issue_type", ""),
                    issue.get("description", ""),
                    issue.get("category", ""),
                ])
        return str(self._path)


class SqliteIssueReportWriter:
    def __init__(self, db):
        self._db = db
    def write(self, issues: list[dict]) -> str:
        for issue in issues:
            self._db.save_report(
                url=issue.get("url", ""),
                status=issue.get("category", "issue"),
                scenario_id="",
                findings=issue.get("description", ""),
                duration=0.0,
            )
        return f"sqlite:{self._db._path} (qa_reports, {len(issues)} rows)"


# -- scenario reports ------------------------------------------------------

class CsvScenarioReportWriter:
    def __init__(self, path: str = "qa_scenarios_report.csv"):
        self._path = Path(path)
    def write(self, results: list) -> str:
        with open(self._path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Scenario ID", "Section", "Title", "Status",
                "Duration (s)", "Steps", "Findings", "Error"
            ])
            for r in results:
                writer.writerow([
                    r.scenario_id,
                    r.section,
                    r.title,
                    r.status,
                    round(r.duration_seconds, 1),
                    r.steps_attempted,
                    r.findings[:500],
                    r.error_message,
                ])
        return str(self._path)


class SqliteScenarioReportWriter:
    def __init__(self, db):
        self._db = db
    def write(self, results: list) -> str:
        for r in results:
            self._db.save_report(
                url="",
                status=r.status,
                scenario_id=str(r.scenario_id),
                findings=r.findings,
                duration=r.duration_seconds,
            )
        return f"sqlite:{self._db._path} (qa_reports, {len(results)} rows)"


# -- snapshots -------------------------------------------------------------

class JsonSnapshotRepository:
    def save(self, url: str, html: str, screenshot: str) -> str:
        from infra.storage import save_reference
        return str(save_reference(url, html, screenshot))
    def load(self, url: str) -> Optional[dict]:
        from infra.storage import load_reference
        return load_reference(url)
    def exists(self, url: str) -> bool:
        from infra.storage import reference_exists
        return reference_exists(url)


# ==========================================================================
# Public accessors — used by tools, runners, etc.
# ==========================================================================

def browser():
    """Return the canonical BrowserManager singleton."""
    from infra.browser import get_browser_manager as _gbm
    return _gbm()


def credentials() -> CredentialRepository:
    return _credentials


def issue_reports() -> IssueReportWriter:
    return _issue_reports


def scenario_reports() -> ScenarioReportWriter:
    return _scenario_reports


def snapshots() -> SnapshotRepository:
    return _snapshots


# ==========================================================================
# ONE LINE TO RULE THEM ALL — change the implementation here
# ==========================================================================
# To switch backends, just swap the line below.  Everything else stays put.
#   JSON / CSV file backend:
_credentials          = JsonCredentialRepository()
_issue_reports        = CsvIssueReportWriter()
_scenario_reports     = CsvScenarioReportWriter()
_snapshots            = JsonSnapshotRepository()

#   SQLite backend (uncomment the 4 lines below, comment out the 4 above):
# from infra.db import get_db as _get_db  # noqa: E402
# _credentials          = SqliteCredentialRepository(_get_db())
# _issue_reports        = SqliteIssueReportWriter(_get_db())
# _scenario_reports     = SqliteScenarioReportWriter(_get_db())

