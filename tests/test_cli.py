"""Integration tests for the CLI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from forge_triage.db import (
    SqlWriteBlockedError,
    execute_sql,
    list_notifications,
    upsert_notification,
)
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


def test_ls_empty_db(tmp_db: sqlite3.Connection) -> None:
    """Empty DB yields no notifications."""
    rows = list_notifications(tmp_db)
    assert rows == []


def test_ls_shows_notifications(tmp_db: sqlite3.Connection) -> None:
    """DB with data returns notification list with expected fields."""
    upsert_notification(
        tmp_db,
        NotificationRow(priority_score=1000, priority_tier="blocking").as_dict(),
    )
    rows = list_notifications(tmp_db)
    assert len(rows) == 1
    assert rows[0].subject_title == "python313: 3.13.1 -> 3.13.2"
    assert rows[0].reason == "review_requested"
    assert rows[0].priority_tier == "blocking"
