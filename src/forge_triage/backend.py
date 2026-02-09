"""Backend worker — processes request queue, dispatches to GitHub/DB."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

from forge_triage.db import delete_notification, upsert_comments
from forge_triage.github import fetch_comments, mark_as_read
from forge_triage.messages import (
    ErrorResult,
    FetchCommentsRequest,
    FetchCommentsResult,
    MarkDoneRequest,
    MarkDoneResult,
    PreLoadCommentsRequest,
    PreLoadComplete,
)

if TYPE_CHECKING:
    import sqlite3

logger = logging.getLogger(__name__)

COMMENT_CONCURRENCY = 5


async def _handle_mark_done(
    req: MarkDoneRequest,
    conn: sqlite3.Connection,
    token: str,
) -> MarkDoneResult:
    """Mark notifications as read on GitHub and delete locally."""
    errors: list[str] = []
    done_ids: list[str] = []
    for nid in req.notification_ids:
        try:
            await mark_as_read(token, nid)
            delete_notification(conn, nid)
            done_ids.append(nid)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{nid}: {e}")
    return MarkDoneResult(notification_ids=done_ids, errors=errors)


async def _handle_fetch_comments(
    req: FetchCommentsRequest,
    conn: sqlite3.Connection,
    token: str,
) -> FetchCommentsResult:
    """Fetch comments for a single notification."""
    row = conn.execute(
        "SELECT raw_json FROM notifications WHERE notification_id = ?",
        (req.notification_id,),
    ).fetchone()
    if row is None:
        return FetchCommentsResult(notification_id=req.notification_id, comment_count=0)

    notif = json.loads(row["raw_json"])
    subject_url: str = notif["subject"]["url"]

    # Build comments URL
    if "/pulls/" in subject_url:
        comments_url = subject_url.replace("/pulls/", "/issues/") + "/comments"
    elif "/issues/" in subject_url:
        comments_url = subject_url + "/comments"
    else:
        return FetchCommentsResult(notification_id=req.notification_id, comment_count=0)

    raw_comments = await fetch_comments(token, comments_url)
    db_comments = [
        {
            "comment_id": str(c["id"]),
            "notification_id": req.notification_id,
            "author": c["user"]["login"],
            "body": c["body"],
            "created_at": c["created_at"],
            "updated_at": c["updated_at"],
        }
        for c in raw_comments
    ]
    upsert_comments(conn, db_comments)
    conn.execute(
        "UPDATE notifications SET comments_loaded = 1 WHERE notification_id = ?",
        (req.notification_id,),
    )
    conn.commit()
    return FetchCommentsResult(notification_id=req.notification_id, comment_count=len(db_comments))


async def _handle_preload(
    req: PreLoadCommentsRequest,
    conn: sqlite3.Connection,
    token: str,
) -> PreLoadComplete:
    """Pre-load comments for top N notifications by priority."""
    rows = conn.execute(
        "SELECT notification_id FROM notifications "
        "WHERE comments_loaded = 0 "
        "ORDER BY priority_score DESC LIMIT ?",
        (req.top_n,),
    ).fetchall()

    sem = asyncio.Semaphore(COMMENT_CONCURRENCY)
    loaded: list[str] = []

    async def _load(nid: str) -> None:
        async with sem:
            result = await _handle_fetch_comments(
                FetchCommentsRequest(notification_id=nid), conn, token
            )
            if result.comment_count > 0:
                loaded.append(nid)

    await asyncio.gather(*[_load(row["notification_id"]) for row in rows])
    return PreLoadComplete(loaded_ids=loaded)


async def backend_worker(
    request_queue: asyncio.Queue[MarkDoneRequest | FetchCommentsRequest | PreLoadCommentsRequest],
    response_queue: asyncio.Queue[
        MarkDoneResult | FetchCommentsResult | PreLoadComplete | ErrorResult
    ],
    conn: sqlite3.Connection,
    token: str,
) -> None:
    """Process requests from the TUI and post results back."""
    while True:
        req = await request_queue.get()
        try:
            result: MarkDoneResult | FetchCommentsResult | PreLoadComplete | ErrorResult
            if isinstance(req, MarkDoneRequest):
                result = await _handle_mark_done(req, conn, token)
            elif isinstance(req, FetchCommentsRequest):
                result = await _handle_fetch_comments(req, conn, token)
            elif isinstance(req, PreLoadCommentsRequest):
                result = await _handle_preload(req, conn, token)
            else:
                result = ErrorResult(request_type=type(req).__name__, error="Unknown request type")
            await response_queue.put(result)
        except Exception as e:  # noqa: BLE001
            await response_queue.put(ErrorResult(request_type=type(req).__name__, error=str(e)))
        finally:
            request_queue.task_done()
