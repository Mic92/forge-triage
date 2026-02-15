"""CRUD operations for PR-specific cached data (details, reviews, comments, files)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3


@dataclass
class PRDetails:
    """Cached PR metadata."""

    notification_id: str
    pr_number: int
    author: str
    body: str | None
    labels_json: str
    base_ref: str | None
    head_ref: str | None
    loaded_at: str


@dataclass
class ReviewComment:
    """A review comment (part of a review thread)."""

    comment_id: str
    review_id: str | None
    notification_id: str
    thread_id: str | None
    author: str
    body: str
    path: str | None
    diff_hunk: str | None
    line: int | None
    side: str | None
    in_reply_to_id: str | None
    is_resolved: int
    created_at: str
    updated_at: str


@dataclass
class PRFile:
    """A changed file in a PR."""

    file_id: int
    notification_id: str
    filename: str
    status: str
    additions: int
    deletions: int
    patch: str | None


# --- Upsert functions ---


def upsert_pr_details(
    conn: sqlite3.Connection,
    row: dict[str, str | int | None],
) -> None:
    """Insert or update cached PR details."""
    conn.execute(
        """INSERT INTO pr_details
           (notification_id, pr_number, author, body, labels_json, base_ref, head_ref)
           VALUES
           (:notification_id, :pr_number, :author, :body, :labels_json, :base_ref, :head_ref)
           ON CONFLICT(notification_id) DO UPDATE SET
            pr_number = excluded.pr_number,
            author = excluded.author,
            body = excluded.body,
            labels_json = excluded.labels_json,
            base_ref = excluded.base_ref,
            head_ref = excluded.head_ref,
            loaded_at = datetime('now')""",
        row,
    )
    conn.commit()


def upsert_pr_reviews(
    conn: sqlite3.Connection,
    reviews: list[dict[str, str | int | None]],
) -> None:
    """Insert or update PR reviews."""
    for review in reviews:
        conn.execute(
            """INSERT INTO pr_reviews
               (review_id, notification_id, author, state, body, submitted_at)
               VALUES
               (:review_id, :notification_id, :author, :state, :body, :submitted_at)
               ON CONFLICT(review_id) DO UPDATE SET
                state = excluded.state,
                body = excluded.body""",
            review,
        )
    conn.commit()


def upsert_review_comments(
    conn: sqlite3.Connection,
    comments: list[dict[str, str | int | None]],
) -> None:
    """Insert or update review comments."""
    for comment in comments:
        conn.execute(
            """INSERT INTO review_comments
               (comment_id, review_id, notification_id, thread_id, author, body,
                path, diff_hunk, line, side, in_reply_to_id, is_resolved,
                created_at, updated_at)
               VALUES
               (:comment_id, :review_id, :notification_id, :thread_id, :author, :body,
                :path, :diff_hunk, :line, :side, :in_reply_to_id, :is_resolved,
                :created_at, :updated_at)
               ON CONFLICT(comment_id) DO UPDATE SET
                body = excluded.body,
                is_resolved = excluded.is_resolved,
                updated_at = excluded.updated_at""",
            comment,
        )
    conn.commit()


def upsert_pr_files(
    conn: sqlite3.Connection,
    files: list[dict[str, str | int | None]],
) -> None:
    """Insert PR changed files. Replaces all files for the notification."""
    if not files:
        return
    notification_id = files[0]["notification_id"]
    conn.execute(
        "DELETE FROM pr_files WHERE notification_id = ?",
        (notification_id,),
    )
    for f in files:
        conn.execute(
            """INSERT INTO pr_files
               (notification_id, filename, status, additions, deletions, patch)
               VALUES
               (:notification_id, :filename, :status, :additions, :deletions, :patch)""",
            f,
        )
    conn.commit()


# --- Query functions ---


def get_pr_details(conn: sqlite3.Connection, notification_id: str) -> PRDetails | None:
    """Return cached PR details, or None if not cached."""
    row = conn.execute(
        "SELECT * FROM pr_details WHERE notification_id = ?",
        (notification_id,),
    ).fetchone()
    if row is None:
        return None
    return PRDetails(
        notification_id=row["notification_id"],
        pr_number=row["pr_number"],
        author=row["author"],
        body=row["body"],
        labels_json=row["labels_json"],
        base_ref=row["base_ref"],
        head_ref=row["head_ref"],
        loaded_at=row["loaded_at"],
    )


def get_review_threads(
    conn: sqlite3.Connection,
    notification_id: str,
) -> list[ReviewComment]:
    """Return review comments for a notification, ordered by created_at."""
    rows = conn.execute(
        "SELECT * FROM review_comments WHERE notification_id = ? ORDER BY created_at",
        (notification_id,),
    ).fetchall()
    return [
        ReviewComment(
            comment_id=r["comment_id"],
            review_id=r["review_id"],
            notification_id=r["notification_id"],
            thread_id=r["thread_id"],
            author=r["author"],
            body=r["body"],
            path=r["path"],
            diff_hunk=r["diff_hunk"],
            line=r["line"],
            side=r["side"],
            in_reply_to_id=r["in_reply_to_id"],
            is_resolved=r["is_resolved"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )
        for r in rows
    ]


def get_pr_files(conn: sqlite3.Connection, notification_id: str) -> list[PRFile]:
    """Return changed files for a notification, ordered by filename."""
    rows = conn.execute(
        "SELECT * FROM pr_files WHERE notification_id = ? ORDER BY filename",
        (notification_id,),
    ).fetchall()
    return [
        PRFile(
            file_id=r["file_id"],
            notification_id=r["notification_id"],
            filename=r["filename"],
            status=r["status"],
            additions=r["additions"],
            deletions=r["deletions"],
            patch=r["patch"],
        )
        for r in rows
    ]


# --- Cache invalidation ---


def delete_pr_data_for_notification(
    conn: sqlite3.Connection,
    notification_id: str,
) -> None:
    """Delete all cached PR data for a notification without deleting the notification itself."""
    conn.execute("DELETE FROM pr_files WHERE notification_id = ?", (notification_id,))
    conn.execute("DELETE FROM review_comments WHERE notification_id = ?", (notification_id,))
    conn.execute("DELETE FROM pr_reviews WHERE notification_id = ?", (notification_id,))
    conn.execute("DELETE FROM pr_details WHERE notification_id = ?", (notification_id,))
    conn.commit()
