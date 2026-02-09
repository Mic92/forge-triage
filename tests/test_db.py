"""Integration tests for the database layer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from forge_triage.db import (
    delete_notification,
    get_comments,
    upsert_comments,
    upsert_notification,
)
from tests.conftest import NotificationRow

if TYPE_CHECKING:
    import sqlite3


def test_upsert_resets_comments_loaded_on_update(tmp_db: sqlite3.Connection) -> None:
    """When updated_at changes, comments_loaded resets to 0."""
    row = NotificationRow(comments_loaded=1)
    upsert_notification(tmp_db, row.as_dict())

    # Verify comments_loaded was set
    result = tmp_db.execute(
        "SELECT comments_loaded FROM notifications WHERE notification_id = ?",
        (row.notification_id,),
    ).fetchone()
    assert result["comments_loaded"] == 1

    # Update with new timestamp
    updated = NotificationRow(updated_at="2026-02-10T08:00:00Z", comments_loaded=1)
    upsert_notification(tmp_db, updated.as_dict())

    result = tmp_db.execute(
        "SELECT comments_loaded FROM notifications WHERE notification_id = ?",
        (row.notification_id,),
    ).fetchone()
    assert result["comments_loaded"] == 0


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
    assert result[0]["author"] == "bob"
    assert result[1]["author"] == "alice"


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
