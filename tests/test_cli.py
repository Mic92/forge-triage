"""Integration tests for the CLI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from forge_triage.cli import _parse_ref
from forge_triage.db import (
    execute_sql,
    list_notifications,
    upsert_notification,
)
from tests.conftest import NotificationRow

if TYPE_CHECKING:
    import sqlite3

import pytest


def test_parse_ref_valid() -> None:
    """_parse_ref returns (owner, repo, number) for valid refs."""
    assert _parse_ref("NixOS/nixpkgs#12345") == ("NixOS", "nixpkgs", 12345)
    assert _parse_ref("org/my-repo#1") == ("org", "my-repo", 1)


def test_parse_ref_missing_hash() -> None:
    """_parse_ref exits on ref without #."""
    with pytest.raises(SystemExit):
        _parse_ref("NixOS/nixpkgs")


def test_parse_ref_missing_owner() -> None:
    """_parse_ref exits on ref without owner/ prefix."""
    with pytest.raises(SystemExit):
        _parse_ref("nixpkgs#123")


def test_parse_ref_non_numeric_number() -> None:
    """_parse_ref exits when number part is not a digit."""
    with pytest.raises(SystemExit):
        _parse_ref("NixOS/nixpkgs#abc")


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
