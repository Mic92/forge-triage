"""Integration tests for the database layer."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from forge_triage.db import (
    delete_notification,
    get_comments,
    get_notification,
    get_sync_meta,
    init_db,
    upsert_comments,
    upsert_notification,
)
from tests.conftest import NotificationRow

if TYPE_CHECKING:
    from pathlib import Path


def test_upsert_resets_comments_loaded_on_update(tmp_db: sqlite3.Connection) -> None:
    """When updated_at changes, comments_loaded resets to 0."""
    row = NotificationRow(comments_loaded=1)
    upsert_notification(tmp_db, row.as_dict())

    # Verify comments_loaded was set
    result = get_notification(tmp_db, row.notification_id)
    assert result is not None
    assert result.comments_loaded == 1

    # Update with new timestamp
    updated = NotificationRow(updated_at="2026-02-10T08:00:00Z", comments_loaded=1)
    upsert_notification(tmp_db, updated.as_dict())

    result = get_notification(tmp_db, row.notification_id)
    assert result is not None
    assert result.comments_loaded == 0


def test_comments_insert_query_and_ordering(tmp_db: sqlite3.Connection) -> None:
    """Insert comments, query by notification_id, verify ordered by created_at."""
    upsert_notification(tmp_db, NotificationRow().as_dict())

    comments = [
        {
            "comment_id": "c2",
            "notification_id": "1001",
            "author": "alice",
            "body": "Second comment",
            "created_at": "2026-02-09T07:10:00Z",
            "updated_at": "2026-02-09T07:10:00Z",
        },
        {
            "comment_id": "c1",
            "notification_id": "1001",
            "author": "bob",
            "body": "First comment",
            "created_at": "2026-02-09T07:00:00Z",
            "updated_at": "2026-02-09T07:00:00Z",
        },
    ]
    upsert_comments(tmp_db, comments)

    result = get_comments(tmp_db, "1001")
    assert len(result) == 2
    assert result[0].author == "bob"
    assert result[1].author == "alice"


def test_comments_cascade_delete(tmp_db: sqlite3.Connection) -> None:
    """Deleting a notification cascades to its comments."""
    upsert_notification(tmp_db, NotificationRow().as_dict())
    upsert_comments(
        tmp_db,
        [
            {
                "comment_id": "c1",
                "notification_id": "1001",
                "author": "bob",
                "body": "A comment",
                "created_at": "2026-02-09T07:00:00Z",
                "updated_at": "2026-02-09T07:00:00Z",
            },
        ],
    )

    delete_notification(tmp_db, "1001")
    assert get_comments(tmp_db, "1001") == []


# ---------- Schema migration tests ----------

_LEGACY_SCHEMA = """\
CREATE TABLE IF NOT EXISTS notifications (
    notification_id   TEXT PRIMARY KEY,
    repo_owner        TEXT NOT NULL,
    repo_name         TEXT NOT NULL,
    subject_type      TEXT NOT NULL,
    subject_title     TEXT NOT NULL,
    subject_url       TEXT,
    html_url          TEXT,
    reason            TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    unread            INTEGER NOT NULL DEFAULT 1,
    priority_score    INTEGER NOT NULL DEFAULT 0,
    priority_tier     TEXT NOT NULL DEFAULT 'fyi',
    raw_json          TEXT NOT NULL,
    comments_loaded   INTEGER NOT NULL DEFAULT 0,
    last_viewed_at    TEXT,
    ci_status         TEXT
);
CREATE TABLE IF NOT EXISTS comments (
    comment_id        TEXT PRIMARY KEY,
    notification_id   TEXT NOT NULL
        REFERENCES notifications(notification_id) ON DELETE CASCADE,
    author            TEXT NOT NULL,
    body              TEXT NOT NULL,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sync_metadata (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _create_legacy_db(path: Path) -> sqlite3.Connection:
    """Create a legacy (version 0) database without subject_state column."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    conn.executescript(_LEGACY_SCHEMA)
    return conn


def test_migration_legacy_db_gets_subject_state(tmp_path: Path) -> None:
    """Legacy DB (v0, no subject_state) gains subject_state column after init_db."""
    db_path = tmp_path / "legacy.db"
    legacy = _create_legacy_db(db_path)
    # Insert a row in the legacy schema (no subject_state column)
    legacy.execute(
        "INSERT INTO notifications "
        "(notification_id, repo_owner, repo_name, subject_type, subject_title, "
        " reason, updated_at, unread, raw_json) "
        "VALUES ('n1', 'NixOS', 'nixpkgs', 'PullRequest', 'Fix bug', "
        " 'review_requested', '2026-01-01T00:00:00Z', 1, '{}')",
    )
    legacy.commit()
    legacy.close()

    # Re-open via init_db which should run migrations
    conn = init_db(db_path)

    # subject_state column must exist
    row = conn.execute(
        "SELECT subject_state FROM notifications WHERE notification_id = 'n1'"
    ).fetchone()
    assert row is not None
    assert row["subject_state"] is None  # existing rows get NULL

    # schema_version must be set to latest
    assert get_sync_meta(conn, "schema_version") == "2"
    conn.close()


def test_migration_idempotent(tmp_path: Path) -> None:
    """Running init_db twice on the same DB causes no errors."""
    db_path = tmp_path / "idem.db"
    conn1 = init_db(db_path)
    conn1.close()

    conn2 = init_db(db_path)
    version = get_sync_meta(conn2, "schema_version")
    assert version == "2"
    conn2.close()


def test_fresh_db_has_subject_state(tmp_path: Path) -> None:
    """A brand-new DB created with init_db has subject_state and latest schema_version."""
    db_path = tmp_path / "fresh.db"
    conn = init_db(db_path)

    # Check subject_state exists in schema
    cols = conn.execute("PRAGMA table_info(notifications)").fetchall()
    col_names = [c["name"] for c in cols]
    assert "subject_state" in col_names

    # schema_version set to latest
    assert get_sync_meta(conn, "schema_version") == "2"
    conn.close()
