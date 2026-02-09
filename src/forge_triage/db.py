"""SQLite schema, queries, and connection management."""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

_SCHEMA = """\
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
    ci_status         TEXT,
    subject_state     TEXT
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

CREATE INDEX IF NOT EXISTS idx_notifications_priority
    ON notifications(priority_score DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_repo
    ON notifications(repo_owner, repo_name);
CREATE INDEX IF NOT EXISTS idx_comments_notification
    ON comments(notification_id, created_at);
"""


# --- Schema migration system ---
# Each migration is (version, sql). Applied in order for DBs behind the latest version.
_MIGRATIONS: list[tuple[int, str]] = [
    (1, "ALTER TABLE notifications ADD COLUMN subject_state TEXT"),
]

_LATEST_VERSION = _MIGRATIONS[-1][0] if _MIGRATIONS else 0


def _get_schema_version(conn: sqlite3.Connection) -> int:
    """Read schema_version from sync_metadata, default 0 for legacy DBs."""
    row = conn.execute("SELECT value FROM sync_metadata WHERE key = 'schema_version'").fetchone()
    return int(row["value"]) if row else 0


def _set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    """Write schema_version to sync_metadata."""
    conn.execute(
        "INSERT INTO sync_metadata (key, value) VALUES ('schema_version', ?)"
        " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(version),),
    )


def _is_fresh_db(conn: sqlite3.Connection) -> bool:
    """Detect a freshly-created DB (no rows, no schema_version set)."""
    row = conn.execute("SELECT value FROM sync_metadata WHERE key = 'schema_version'").fetchone()
    if row is not None:
        return False
    count: int = conn.execute("SELECT count(*) FROM notifications").fetchone()[0]
    return count == 0


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Apply pending migrations or stamp fresh DBs at the latest version.

    Fresh databases already have the full up-to-date schema from CREATE TABLE,
    so we only stamp them at the latest version without running ALTER statements.
    Existing databases get each pending migration applied sequentially.
    """
    if _is_fresh_db(conn):
        _set_schema_version(conn, _LATEST_VERSION)
        conn.commit()
        return

    current_version = _get_schema_version(conn)
    for version, sql in _MIGRATIONS:
        if version > current_version:
            conn.execute(sql)
            current_version = version

    _set_schema_version(conn, current_version)
    conn.commit()


def get_db_path() -> Path:
    """Return the path to the SQLite database, following XDG conventions."""
    xdg_data = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg_data) if xdg_data else Path.home() / ".local" / "share"
    return base / "forge-triage" / "notifications.db"


def init_db(path: Path) -> sqlite3.Connection:
    """Create or open the database and ensure the schema exists.

    For fresh databases, the full up-to-date schema is applied and stamped
    with the latest version.  For existing databases, pending migrations
    are applied sequentially.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    _run_migrations(conn)
    return conn


def open_db() -> sqlite3.Connection:
    """Open the database at the default XDG path."""
    return init_db(get_db_path())


def upsert_notification(conn: sqlite3.Connection, row: dict[str, str | int | None]) -> None:
    """Insert or update a notification. Resets comments_loaded when updated_at changes."""
    existing = conn.execute(
        "SELECT updated_at FROM notifications WHERE notification_id = ?",
        (row["notification_id"],),
    ).fetchone()

    if existing is None:
        conn.execute(
            """INSERT INTO notifications
               (notification_id, repo_owner, repo_name, subject_type, subject_title,
                subject_url, html_url, reason, updated_at, unread, priority_score,
                priority_tier, raw_json, comments_loaded, last_viewed_at, ci_status,
                subject_state)
               VALUES
               (:notification_id, :repo_owner, :repo_name, :subject_type, :subject_title,
                :subject_url, :html_url, :reason, :updated_at, :unread, :priority_score,
                :priority_tier, :raw_json, :comments_loaded, :last_viewed_at, :ci_status,
                :subject_state)""",
            row,
        )
    else:
        # Reset comments_loaded if updated_at changed
        updated_at_changed = existing["updated_at"] != row["updated_at"]
        comments_loaded = 0 if updated_at_changed else row["comments_loaded"]
        conn.execute(
            """UPDATE notifications SET
                repo_owner = :repo_owner, repo_name = :repo_name,
                subject_type = :subject_type, subject_title = :subject_title,
                subject_url = :subject_url, html_url = :html_url,
                reason = :reason, updated_at = :updated_at, unread = :unread,
                priority_score = :priority_score, priority_tier = :priority_tier,
                raw_json = :raw_json, comments_loaded = :comments_loaded,
                ci_status = :ci_status, subject_state = :subject_state
               WHERE notification_id = :notification_id""",
            {**row, "comments_loaded": comments_loaded},
        )
    conn.commit()


def upsert_comments(conn: sqlite3.Connection, comments: list[dict[str, str]]) -> None:
    """Insert or update comments."""
    for comment in comments:
        conn.execute(
            """INSERT INTO comments
               (comment_id, notification_id, author, body, created_at, updated_at)
               VALUES
               (:comment_id, :notification_id, :author, :body, :created_at, :updated_at)
               ON CONFLICT(comment_id) DO UPDATE SET
                body = excluded.body,
                updated_at = excluded.updated_at""",
            comment,
        )
    conn.commit()


def get_comments(conn: sqlite3.Connection, notification_id: str) -> list[sqlite3.Row]:
    """Return comments for a notification, ordered by created_at."""
    return conn.execute(
        "SELECT * FROM comments WHERE notification_id = ? ORDER BY created_at",
        (notification_id,),
    ).fetchall()


def get_sync_meta(conn: sqlite3.Connection, key: str) -> str | None:
    """Return a sync metadata value, or None if not set."""
    row = conn.execute("SELECT value FROM sync_metadata WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_sync_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    """Set a sync metadata value (insert or update)."""
    conn.execute(
        "INSERT INTO sync_metadata (key, value) VALUES (?, ?)"
        " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()


def delete_notification(conn: sqlite3.Connection, notification_id: str) -> None:
    """Delete a notification and its associated comments (via CASCADE)."""
    conn.execute(
        "DELETE FROM notifications WHERE notification_id = ?",
        (notification_id,),
    )
    conn.commit()


_WRITE_KEYWORDS = ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE")


class SqlWriteBlockedError(Exception):
    """Raised when a write operation is attempted without --write."""


@dataclass
class SqlResult:
    """Result of a SQL query execution."""

    columns: list[str] | None
    rows: list[tuple[object, ...]]
    is_write: bool


def execute_sql(
    conn: sqlite3.Connection,
    query: str,
    *,
    allow_write: bool = False,
) -> SqlResult:
    """Execute a raw SQL query, optionally blocking writes.

    Raises:
        SqlWriteBlockedError: If query is a write operation and allow_write is False.
    """
    stripped = query.strip().upper()
    is_write = any(stripped.startswith(kw) for kw in _WRITE_KEYWORDS)

    if is_write and not allow_write:
        msg = "Write operations are blocked by default. Use --write to allow."
        raise SqlWriteBlockedError(msg)

    cursor = conn.execute(query)

    if cursor.description is None:
        conn.commit()
        return SqlResult(columns=None, rows=[], is_write=True)

    columns = [d[0] for d in cursor.description]
    rows = [tuple(row) for row in cursor.fetchall()]
    return SqlResult(columns=columns, rows=rows, is_write=False)
