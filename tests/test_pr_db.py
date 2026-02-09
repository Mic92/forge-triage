"""Tests for the PR data caching layer (pr_db)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from forge_triage.db import upsert_notification

if TYPE_CHECKING:
    import sqlite3
from forge_triage.pr_db import (
    get_pr_details,
    get_pr_files,
    get_review_threads,
    upsert_pr_details,
    upsert_pr_files,
    upsert_pr_reviews,
    upsert_review_comments,
)
from tests.conftest import NotificationRow


def _insert_notification(conn: sqlite3.Connection, nid: str = "1001") -> None:
    """Helper: insert a notification so FK constraints are satisfied."""
    upsert_notification(conn, NotificationRow(notification_id=nid).as_dict())


def _seed_full_pr(conn: sqlite3.Connection, nid: str = "1001") -> None:
    """Insert notification + pr_details + review + comment + file for cascade testing."""
    _insert_notification(conn, nid)
    upsert_pr_details(
        conn,
        {
            "notification_id": nid,
            "pr_number": 12345,
            "author": "contributor",
            "body": "desc",
            "labels_json": "[]",
            "base_ref": "main",
            "head_ref": "branch",
        },
    )
    upsert_pr_reviews(
        conn,
        [
            {
                "review_id": f"r1-{nid}",
                "notification_id": nid,
                "author": "reviewer",
                "state": "COMMENTED",
                "body": "",
                "submitted_at": "2026-02-09T08:00:00Z",
            },
        ],
    )
    upsert_review_comments(
        conn,
        [
            {
                "comment_id": f"rc1-{nid}",
                "review_id": f"r1-{nid}",
                "notification_id": nid,
                "thread_id": "t1",
                "author": "reviewer",
                "body": "Fix this",
                "path": "src/main.py",
                "diff_hunk": "@@ -1,3 +1,5 @@",
                "line": 5,
                "side": "RIGHT",
                "in_reply_to_id": None,
                "is_resolved": 0,
                "created_at": "2026-02-09T08:00:00Z",
                "updated_at": "2026-02-09T08:00:00Z",
            },
        ],
    )
    upsert_pr_files(
        conn,
        [
            {
                "notification_id": nid,
                "filename": "src/main.py",
                "status": "modified",
                "additions": 5,
                "deletions": 2,
                "patch": "@@ -1 +1 @@",
            },
        ],
    )


def test_pr_details_upsert_updates_on_conflict(tmp_db: sqlite3.Connection) -> None:
    """Upserting PR details twice updates the record rather than duplicating."""
    _insert_notification(tmp_db)
    base: dict[str, str | int | None] = {
        "notification_id": "1001",
        "pr_number": 12345,
        "author": "contributor",
        "body": "Old body",
        "labels_json": "[]",
        "base_ref": "main",
        "head_ref": "branch-1",
    }
    upsert_pr_details(tmp_db, base)
    upsert_pr_details(tmp_db, {**base, "body": "New body", "labels_json": '["updated"]'})

    result = get_pr_details(tmp_db, "1001")
    assert result is not None
    assert result.body == "New body"
    assert result.labels_json == '["updated"]'
    assert result.loaded_at is not None


def test_review_comments_round_trip(tmp_db: sqlite3.Connection) -> None:
    """Insert review + comments and verify dataclass fields survive the round-trip."""
    _insert_notification(tmp_db)
    upsert_pr_reviews(
        tmp_db,
        [
            {
                "review_id": "r1",
                "notification_id": "1001",
                "author": "reviewer1",
                "state": "COMMENTED",
                "body": "",
                "submitted_at": "2026-02-09T08:00:00Z",
            },
        ],
    )
    upsert_review_comments(
        tmp_db,
        [
            {
                "comment_id": "rc1",
                "review_id": "r1",
                "notification_id": "1001",
                "thread_id": "t1",
                "author": "reviewer1",
                "body": "Needs a docstring",
                "path": "src/main.py",
                "diff_hunk": "@@ -10,6 +10,8 @@",
                "line": 15,
                "side": "RIGHT",
                "in_reply_to_id": None,
                "is_resolved": 0,
                "created_at": "2026-02-09T08:00:00Z",
                "updated_at": "2026-02-09T08:00:00Z",
            },
        ],
    )
    threads = get_review_threads(tmp_db, "1001")
    assert len(threads) == 1
    c = threads[0]
    assert c.comment_id == "rc1"
    assert c.body == "Needs a docstring"
    assert c.path == "src/main.py"
    assert c.line == 15
    assert c.is_resolved == 0


def test_pr_files_round_trip_including_null_patch(tmp_db: sqlite3.Connection) -> None:
    """Insert files with and without patches; verify NULL patch for binary files."""
    _insert_notification(tmp_db)
    upsert_pr_files(
        tmp_db,
        [
            {
                "notification_id": "1001",
                "filename": "src/main.py",
                "status": "modified",
                "additions": 10,
                "deletions": 3,
                "patch": "@@ -1,5 +1,12 @@\n+import sys\n",
            },
            {
                "notification_id": "1001",
                "filename": "image.png",
                "status": "added",
                "additions": 0,
                "deletions": 0,
                "patch": None,
            },
        ],
    )
    files = get_pr_files(tmp_db, "1001")
    assert len(files) == 2
    by_name = {f.filename: f for f in files}
    assert by_name["src/main.py"].additions == 10
    assert by_name["src/main.py"].patch is not None
    assert by_name["image.png"].patch is None


def test_cascade_delete_through_full_chain(tmp_db: sqlite3.Connection) -> None:
    """Deleting a notification cascades to pr_details, pr_reviews, review_comments, pr_files."""
    _seed_full_pr(tmp_db, "1001")

    # Sanity: data exists before delete
    assert get_pr_details(tmp_db, "1001") is not None
    assert len(get_review_threads(tmp_db, "1001")) == 1
    assert len(get_pr_files(tmp_db, "1001")) == 1

    tmp_db.execute("DELETE FROM notifications WHERE notification_id = '1001'")
    tmp_db.commit()

    assert get_pr_details(tmp_db, "1001") is None
    assert get_review_threads(tmp_db, "1001") == []
    assert get_pr_files(tmp_db, "1001") == []
