"""SQLite schema, queries, and connection management."""

from __future__ import annotations

import importlib.resources
import os
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

_SCHEMA = importlib.resources.files(__package__).joinpath("schema.sql").read_text()


# --- Data classes ---


@dataclass
class Notification:
    """A GitHub notification row."""

    notification_id: str
    repo_owner: str
    repo_name: str
    subject_type: str
    subject_title: str
    subject_url: str | None
    html_url: str | None
    reason: str
    updated_at: str
    unread: int
    priority_score: int
    priority_tier: str
    raw_json: str
    comments_loaded: int
    last_viewed_at: str | None
    ci_status: str | None
    subject_state: str | None

    def to_dict(self) -> dict[str, str | int | None]:
        """Return a dict suitable for JSON serialization."""
        return asdict(self)

    def meta_line(self, *, bold_ci: bool = True) -> str:
        """Build the metadata line (repo, type, reason, state, CI) for display."""
        parts = [
            f"{self.repo_owner}/{self.repo_name}",
            self.subject_type,
            self.reason,
        ]
        if self.subject_state:
            state_icons = {"open": "🟢", "closed": "🔴", "merged": "🟣"}
            icon = state_icons.get(self.subject_state, "")
            parts.append(f"{icon} {self.subject_state}")
        if self.ci_status:
            ci_icons = {"success": "✅", "failure": "❌", "pending": "⏳"}
            icon = ci_icons.get(self.ci_status, "❓")
            ci_label = "**CI:**" if bold_ci else "CI:"
            parts.append(f"{ci_label} {icon} {self.ci_status}")
        return "  •  ".join(parts)


@dataclass
class Comment:
    """A comment on a notification."""

    comment_id: str
    notification_id: str
    author: str
    body: str
    created_at: str
    updated_at: str


@dataclass
class NotificationPreload:
    """Lightweight notification data for comment pre-loading."""

    notification_id: str
    raw_json: str
    comments_loaded: int


@dataclass
class CountStat:
    """A label + count pair for statistics."""

    label: str
    count: int


@dataclass
class NotificationStats:
    """Aggregate notification statistics."""

    total: int
    by_tier: list[CountStat]
    by_repo: list[CountStat]
    by_reason: list[CountStat]


def _escape_like(text: str) -> str:
    """Escape LIKE special characters so they match literally."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _row_to_notification(row: sqlite3.Row) -> Notification:
    """Convert a sqlite3.Row to a Notification dataclass."""
    return Notification(
        notification_id=row["notification_id"],
        repo_owner=row["repo_owner"],
        repo_name=row["repo_name"],
        subject_type=row["subject_type"],
        subject_title=row["subject_title"],
        subject_url=row["subject_url"],
        html_url=row["html_url"],
        reason=row["reason"],
        updated_at=row["updated_at"],
        unread=row["unread"],
        priority_score=row["priority_score"],
        priority_tier=row["priority_tier"],
        raw_json=row["raw_json"],
        comments_loaded=row["comments_loaded"],
        last_viewed_at=row["last_viewed_at"],
        ci_status=row["ci_status"],
        subject_state=row["subject_state"],
    )


def _row_to_comment(row: sqlite3.Row) -> Comment:
    """Convert a sqlite3.Row to a Comment dataclass."""
    return Comment(
        comment_id=row["comment_id"],
        notification_id=row["notification_id"],
        author=row["author"],
        body=row["body"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# --- Schema migration system ---
# Each migration is (version, sql). Applied in order for DBs behind the latest version.
_MIGRATIONS: list[tuple[int, str]] = [
    (1, "ALTER TABLE notifications ADD COLUMN subject_state TEXT"),
    (
        2,
        # Make review_comments.review_id nullable (was NOT NULL, violating FK on
        # comments without a known review).  SQLite cannot ALTER column constraints,
        # so we recreate the table.  Data is a cache and will be re-fetched.
        "DROP TABLE IF EXISTS review_comments;"
        " CREATE TABLE review_comments ("
        "   comment_id      TEXT PRIMARY KEY,"
        "   review_id       TEXT REFERENCES pr_reviews(review_id) ON DELETE CASCADE,"
        "   notification_id TEXT NOT NULL"
        "       REFERENCES notifications(notification_id) ON DELETE CASCADE,"
        "   thread_id       TEXT,"
        "   author          TEXT NOT NULL,"
        "   body            TEXT NOT NULL,"
        "   path            TEXT,"
        "   diff_hunk       TEXT,"
        "   line            INTEGER,"
        "   side            TEXT,"
        "   in_reply_to_id  TEXT,"
        "   is_resolved     INTEGER NOT NULL DEFAULT 0,"
        "   created_at      TEXT NOT NULL,"
        "   updated_at      TEXT NOT NULL"
        " );"
        " CREATE INDEX IF NOT EXISTS idx_review_comments_notification"
        "   ON review_comments(notification_id, created_at);",
    ),
]

_LATEST_VERSION = _MIGRATIONS[-1][0] if _MIGRATIONS else 0


def get_schema_version(conn: sqlite3.Connection) -> int:
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

    current_version = get_schema_version(conn)
    for version, sql in _MIGRATIONS:
        if version > current_version:
            conn.executescript(sql)
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
    # DB may contain auth-adjacent data (tokens in raw_json); restrict access
    path.parent.chmod(0o700)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    _run_migrations(conn)
    return conn


def open_memory_db() -> sqlite3.Connection:
    """Create an in-memory database with the full schema applied (for tests)."""
    conn = sqlite3.connect(":memory:")
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


def map_raw_comments(
    raw_comments: list[dict[str, Any]],
    notification_id: str,
) -> list[dict[str, str]]:
    """Map raw GitHub API comment dicts to the shape expected by upsert_comments."""
    return [
        {
            "comment_id": str(c["id"]),
            "notification_id": notification_id,
            "author": c["user"]["login"] if c.get("user") else "[deleted]",
            "body": c["body"],
            "created_at": c["created_at"],
            "updated_at": c["updated_at"],
        }
        for c in raw_comments
    ]


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


def get_comments(conn: sqlite3.Connection, notification_id: str) -> list[Comment]:
    """Return comments for a notification, ordered by created_at."""
    rows = conn.execute(
        "SELECT * FROM comments WHERE notification_id = ? ORDER BY created_at",
        (notification_id,),
    ).fetchall()
    return [_row_to_comment(r) for r in rows]


def delete_notification(conn: sqlite3.Connection, notification_id: str) -> None:
    """Delete a notification and its associated comments (via CASCADE)."""
    conn.execute(
        "DELETE FROM notifications WHERE notification_id = ?",
        (notification_id,),
    )
    conn.commit()


# --- Query functions (consolidated from across the codebase) ---


def get_notification(conn: sqlite3.Connection, notification_id: str) -> Notification | None:
    """Return a single notification by ID, or None."""
    row = conn.execute(
        "SELECT * FROM notifications WHERE notification_id = ?",
        (notification_id,),
    ).fetchone()
    return _row_to_notification(row) if row is not None else None


def get_notification_count(conn: sqlite3.Connection) -> int:
    """Return the total number of notifications."""
    count: int = conn.execute("SELECT count(*) FROM notifications").fetchone()[0]
    return count


def list_notifications(
    conn: sqlite3.Connection,
    *,
    filter_text: str = "",
    filter_reason: str = "",
) -> list[Notification]:
    """Return notifications ordered by priority, with optional filters."""
    query = "SELECT * FROM notifications WHERE 1=1"
    params: list[str] = []

    if filter_text:
        query += (
            " AND (subject_title LIKE ? ESCAPE '\\'"
            " OR repo_owner || '/' || repo_name LIKE ? ESCAPE '\\')"
        )
        escaped = _escape_like(filter_text)
        like = f"%{escaped}%"
        params.extend([like, like])

    if filter_reason:
        query += " AND reason = ?"
        params.append(filter_reason)

    query += " ORDER BY priority_score DESC, updated_at DESC"
    return [_row_to_notification(r) for r in conn.execute(query, params).fetchall()]


def get_unloaded_top_notification_ids(
    conn: sqlite3.Connection,
    limit: int,
) -> list[str]:
    """Return IDs of top-N notifications by priority where comments are not yet loaded."""
    rows = conn.execute(
        "SELECT notification_id FROM notifications "
        "WHERE comments_loaded = 0 "
        "ORDER BY priority_score DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [row["notification_id"] for row in rows]


def get_top_notifications_for_preload(
    conn: sqlite3.Connection,
    limit: int,
) -> list[NotificationPreload]:
    """Return top-N notifications by priority for comment pre-loading."""
    rows = conn.execute(
        "SELECT notification_id, raw_json, comments_loaded FROM notifications "
        "ORDER BY priority_score DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [
        NotificationPreload(
            notification_id=r["notification_id"],
            raw_json=r["raw_json"],
            comments_loaded=r["comments_loaded"],
        )
        for r in rows
    ]


def mark_comments_loaded(conn: sqlite3.Connection, notification_id: str) -> None:
    """Set comments_loaded = 1 for a notification."""
    conn.execute(
        "UPDATE notifications SET comments_loaded = 1 WHERE notification_id = ?",
        (notification_id,),
    )
    conn.commit()


def update_last_viewed(conn: sqlite3.Connection, notification_id: str) -> None:
    """Set last_viewed_at to now for a notification."""
    conn.execute(
        "UPDATE notifications SET last_viewed_at = datetime('now') WHERE notification_id = ?",
        (notification_id,),
    )
    conn.commit()


def get_notification_ids_by_reason(
    conn: sqlite3.Connection,
    reason: str,
) -> list[str]:
    """Return notification IDs matching a reason."""
    rows = conn.execute(
        "SELECT notification_id FROM notifications WHERE reason = ?",
        (reason,),
    ).fetchall()
    return [row["notification_id"] for row in rows]


def get_notification_ids_by_repo_title(
    conn: sqlite3.Connection,
    repo: str,
    title_pattern: str,
) -> list[str]:
    """Return notification IDs matching a repo and title pattern.

    The title_pattern is used as a raw LIKE pattern (caller provides wildcards).
    Special characters are NOT escaped here to preserve caller intent.
    """
    rows = conn.execute(
        "SELECT notification_id FROM notifications "
        "WHERE repo_owner || '/' || repo_name = ? "
        "AND subject_title LIKE ? ESCAPE '\\'",
        (repo, title_pattern),
    ).fetchall()
    return [row["notification_id"] for row in rows]


def get_notification_ids_by_ref(
    conn: sqlite3.Connection,
    owner: str,
    repo: str,
    number: int,
) -> list[str]:
    """Return notification IDs matching owner/repo and issue/PR number."""
    rows = conn.execute(
        "SELECT notification_id FROM notifications "
        "WHERE repo_owner = ? AND repo_name = ? "
        "AND subject_url LIKE ?",
        (owner, repo, f"%/{number}"),
    ).fetchall()
    return [row["notification_id"] for row in rows]


def get_notification_stats(conn: sqlite3.Connection) -> NotificationStats:
    """Return aggregate notification statistics."""
    total: int = conn.execute("SELECT count(*) FROM notifications").fetchone()[0]
    by_tier = [
        CountStat(label=r["priority_tier"], count=r["cnt"])
        for r in conn.execute(
            "SELECT priority_tier, count(*) as cnt FROM notifications "
            "GROUP BY priority_tier ORDER BY cnt DESC"
        ).fetchall()
    ]
    by_repo = [
        CountStat(label=r["repo"], count=r["cnt"])
        for r in conn.execute(
            "SELECT repo_owner || '/' || repo_name as repo, count(*) as cnt "
            "FROM notifications GROUP BY repo ORDER BY cnt DESC"
        ).fetchall()
    ]
    by_reason = [
        CountStat(label=r["reason"], count=r["cnt"])
        for r in conn.execute(
            "SELECT reason, count(*) as cnt FROM notifications GROUP BY reason ORDER BY cnt DESC"
        ).fetchall()
    ]
    return NotificationStats(total=total, by_tier=by_tier, by_repo=by_repo, by_reason=by_reason)


def purge_all_notifications(conn: sqlite3.Connection) -> None:
    """Delete all notifications."""
    conn.execute("DELETE FROM notifications")
    conn.commit()


def purge_stale_notifications(
    conn: sqlite3.Connection,
    keep_ids: set[str],
    oldest_updated_at: str,
) -> int:
    """Delete notifications not in keep_ids with updated_at <= oldest_updated_at."""
    placeholders = ",".join("?" for _ in keep_ids)
    cursor = conn.execute(
        f"DELETE FROM notifications WHERE notification_id NOT IN ({placeholders})"  # noqa: S608
        " AND updated_at <= ?",
        [*keep_ids, oldest_updated_at],
    )
    purged = cursor.rowcount
    if purged:
        conn.commit()
    return purged


@dataclass
class SqlResult:
    """Result of a SQL query execution."""

    columns: list[str] | None
    rows: list[tuple[object, ...]]


def execute_sql(
    conn: sqlite3.Connection,
    query: str,
) -> SqlResult:
    """Execute a raw SQL query, optionally blocking writes.

    Raises:
        SqlWriteBlockedError: If query is a write operation and allow_write is False.
    """
    cursor = conn.execute(query)

    if cursor.description is None:
        conn.commit()
        return SqlResult(columns=None, rows=[])

    columns = [d[0] for d in cursor.description]
    rows = [tuple(row) for row in cursor.fetchall()]
    return SqlResult(columns=columns, rows=rows)
