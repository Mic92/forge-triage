"""Integration tests for the CLI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from forge_triage.cli import main
from forge_triage.db import SqlWriteBlockedError, execute_sql, upsert_notification
from tests.conftest import NotificationRow

if TYPE_CHECKING:
    import sqlite3

import pytest


def test_execute_sql_blocks_write_by_default(tmp_db: sqlite3.Connection) -> None:
    """execute_sql raises SqlWriteBlockedError for writes without allow_write."""
    with pytest.raises(SqlWriteBlockedError):
        execute_sql(tmp_db, "DROP TABLE notifications")


def test_execute_sql_allows_read(tmp_db: sqlite3.Connection) -> None:
    """execute_sql permits SELECT queries."""
    result = execute_sql(tmp_db, "SELECT count(*) FROM notifications")
    assert result.columns is not None
    assert result.rows == [(0,)]


def test_ls_empty_db(
    tmp_db: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """ls with empty DB shows inbox-empty message."""
    monkeypatch.setattr("forge_triage.cli.open_db", lambda: tmp_db)
    main(["ls"])
    captured = capsys.readouterr()
    assert "empty" in captured.out.lower()


def test_ls_shows_notifications(
    tmp_db: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """ls with data shows notification table."""
    upsert_notification(
        tmp_db,
        NotificationRow(priority_score=1000, priority_tier="blocking").as_dict(),
    )
    monkeypatch.setattr("forge_triage.cli.open_db", lambda: tmp_db)
    main(["ls"])
    captured = capsys.readouterr()
    assert "python313" in captured.out
    assert "review_requested" in captured.out
