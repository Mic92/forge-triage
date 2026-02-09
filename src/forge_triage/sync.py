"""Sync orchestration — fetch from GitHub, update local DB."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Callable

from forge_triage.db import (
    get_sync_meta,
    set_sync_meta,
    upsert_comments,
    upsert_notification,
)
from forge_triage.github import (
    fetch_comments,
    fetch_notifications,
    fetch_subject_details,
)
from forge_triage.priority import compute_priority

DEFAULT_MAX_NOTIFICATIONS = 1000
COMMENT_PRELOAD_COUNT = 20
COMMENT_CONCURRENCY = 5


@dataclass
class SyncResult:
    """Summary of a sync operation."""

    new: int
    updated: int
    purged: int
    total: int


def _notification_to_row(
    notif: dict[str, Any],
    ci_status: str | None,
    subject_state: str | None,
    priority_score: int,
    priority_tier: str,
) -> dict[str, str | int | None]:
    """Convert a GitHub API notification to a DB row dict."""
    repo = notif["repository"]
    subject = notif["subject"]
    # Convert API URL to browser URL (subject.url can be null for some types)
    subject_url: str | None = subject["url"]
    if subject_url is not None:
        html_url: str | None = (
            subject_url.replace("api.github.com/repos", "github.com")
            .replace("/pulls/", "/pull/")
            .replace("/issues/", "/issues/")
        )
    else:
        html_url = None
    return {
        "notification_id": notif["id"],
        "repo_owner": repo["owner"]["login"],
        "repo_name": repo["name"],
        "subject_type": subject["type"],
        "subject_title": subject["title"],
        "subject_url": subject_url,
        "html_url": html_url,
        "reason": notif["reason"],
        "updated_at": notif["updated_at"],
        "unread": 1 if notif.get("unread", True) else 0,
        "priority_score": priority_score,
        "priority_tier": priority_tier,
        "raw_json": json.dumps(notif),
        "comments_loaded": 0,
        "last_viewed_at": None,
        "ci_status": ci_status,
        "subject_state": subject_state,
    }


def _comments_url_from_notification(notif: dict[str, Any]) -> str | None:
    """Extract the comments URL from a notification's subject."""
    subject_url: str | None = notif["subject"]["url"]
    if subject_url is None:
        return None
    # Convert PR/Issue API URL to comments URL
    # e.g. /repos/NixOS/nixpkgs/pulls/12345 → /repos/NixOS/nixpkgs/issues/12345/comments
    if "/pulls/" in subject_url:
        return subject_url.replace("/pulls/", "/issues/") + "/comments"
    if "/issues/" in subject_url:
        return subject_url + "/comments"
    return None


async def _preload_comments_for_top_n(
    conn: sqlite3.Connection,
    token: str,
    top_n: int = COMMENT_PRELOAD_COUNT,
) -> None:
    """Pre-load comments for the top N notifications by priority."""
    # Sort by priority_score descending (already computed)
    rows = conn.execute(
        "SELECT notification_id, raw_json, comments_loaded FROM notifications "
        "ORDER BY priority_score DESC LIMIT ?",
        (top_n,),
    ).fetchall()

    sem = asyncio.Semaphore(COMMENT_CONCURRENCY)

    async def _load_one(notification_id: str, raw_json: str) -> None:
        async with sem:
            notif = json.loads(raw_json)
            url = _comments_url_from_notification(notif)
            if url is None:
                return
            comments = await fetch_comments(token, url)
            db_comments = [
                {
                    "comment_id": str(c["id"]),
                    "notification_id": notification_id,
                    "author": c["user"]["login"],
                    "body": c["body"],
                    "created_at": c["created_at"],
                    "updated_at": c["updated_at"],
                }
                for c in comments
            ]
            upsert_comments(conn, db_comments)
            conn.execute(
                "UPDATE notifications SET comments_loaded = 1 WHERE notification_id = ?",
                (notification_id,),
            )
            conn.commit()

    tasks = [
        _load_one(row["notification_id"], row["raw_json"])
        for row in rows
        if not row["comments_loaded"]
    ]
    if tasks:
        await asyncio.gather(*tasks)


def _purge_stale(
    conn: sqlite3.Connection,
    fetched_notifications: list[dict[str, Any]],
) -> int:
    """Delete local notifications that GitHub no longer returns.

    If the sync returned zero notifications, all local notifications are purged.
    Otherwise, notifications not in the fetched set whose updated_at is older than
    or equal to the oldest fetched updated_at are deleted (they fall within the
    time window the API covered and were not returned, meaning they're gone).
    """
    if not fetched_notifications:
        # Empty response → inbox is empty on GitHub
        count: int = conn.execute("SELECT count(*) FROM notifications").fetchone()[0]
        if count > 0:
            conn.execute("DELETE FROM notifications")
            conn.commit()
        return count

    fetched_ids = {n["id"] for n in fetched_notifications}
    oldest = min(n["updated_at"] for n in fetched_notifications)

    placeholders = ",".join("?" for _ in fetched_ids)
    cursor = conn.execute(
        f"DELETE FROM notifications WHERE notification_id NOT IN ({placeholders})"  # noqa: S608
        " AND updated_at <= ?",
        [*fetched_ids, oldest],
    )
    purged = cursor.rowcount
    if purged:
        conn.commit()
    return purged


async def sync(
    conn: sqlite3.Connection,
    token: str,
    *,
    max_notifications: int = DEFAULT_MAX_NOTIFICATIONS,
    on_progress: Callable[[int, int], None] | None = None,
) -> SyncResult:
    """Full sync: fetch notifications, compute priorities, pre-load comments."""
    since = get_sync_meta(conn, "last_sync_at")

    # Fetch notifications (capped to avoid unbounded API calls)
    raw_notifications = await fetch_notifications(token, since=since)
    raw_notifications = raw_notifications[:max_notifications]

    # Batch-fetch subject details (state + CI) via GraphQL
    subject_details = await fetch_subject_details(token, raw_notifications)

    new_count = 0
    updated_count = 0
    total_to_process = len(raw_notifications)

    for idx, notif in enumerate(raw_notifications, 1):
        notification_id = notif["id"]

        subject_state, ci_status = subject_details.get(notification_id, (None, None))

        # Compute priority (is_own_pr requires knowing the user — simplified for now)
        score, tier = compute_priority(notif["reason"], ci_status, is_own_pr=False)

        row = _notification_to_row(notif, ci_status, subject_state, score, tier)

        # Check if this is new or updated
        existing = conn.execute(
            "SELECT updated_at FROM notifications WHERE notification_id = ?",
            (notification_id,),
        ).fetchone()
        if existing is None:
            new_count += 1
        elif existing["updated_at"] != notif["updated_at"]:
            updated_count += 1

        upsert_notification(conn, row)

        if on_progress is not None:
            on_progress(idx, total_to_process)

    # Purge stale notifications no longer returned by GitHub
    purged_count = _purge_stale(conn, raw_notifications)

    # Pre-load comments for top priority items
    await _preload_comments_for_top_n(conn, token)

    # Update sync metadata
    if raw_notifications:
        latest = max(n["updated_at"] for n in raw_notifications)
        set_sync_meta(conn, "last_sync_at", latest)

    total = conn.execute("SELECT count(*) FROM notifications").fetchone()[0]

    return SyncResult(new=new_count, updated=updated_count, purged=purged_count, total=total)
