"""Backend worker — processes request queue, dispatches to GitHub/DB."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

from forge_triage.db import (
    delete_notification,
    get_notification,
    get_unloaded_top_notification_ids,
    mark_comments_loaded,
    upsert_comments,
)
from forge_triage.github import fetch_comments, mark_as_read, parse_subject_url
from forge_triage.github_pr import (
    PRRef,
    fetch_pr_files,
    fetch_pr_metadata,
    fetch_review_threads,
    post_review_reply,
    resolve_review_thread,
    submit_review,
    unresolve_review_thread,
)
from forge_triage.messages import (
    ErrorResult,
    FetchCommentsRequest,
    FetchCommentsResult,
    FetchPRDetailRequest,
    FetchPRDetailResult,
    MarkDoneRequest,
    MarkDoneResult,
    PostReviewCommentRequest,
    PostReviewCommentResult,
    PreLoadCommentsRequest,
    PreLoadComplete,
    Request,
    ResolveThreadRequest,
    ResolveThreadResult,
    Response,
    SubmitReviewRequest,
    SubmitReviewResult,
)
from forge_triage.pr_db import (
    delete_pr_data_for_notification,
    upsert_pr_details,
    upsert_pr_files,
    upsert_pr_reviews,
    upsert_review_comments,
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
    return MarkDoneResult(notification_ids=tuple(done_ids), errors=tuple(errors))


async def _handle_fetch_comments(
    req: FetchCommentsRequest,
    conn: sqlite3.Connection,
    token: str,
) -> FetchCommentsResult:
    """Fetch comments for a single notification."""
    notif_row = get_notification(conn, req.notification_id)
    if notif_row is None:
        return FetchCommentsResult(notification_id=req.notification_id, comment_count=0)

    notif = json.loads(notif_row.raw_json)
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
            "author": c["user"]["login"] if c.get("user") else "[deleted]",
            "body": c["body"],
            "created_at": c["created_at"],
            "updated_at": c["updated_at"],
        }
        for c in raw_comments
    ]
    upsert_comments(conn, db_comments)
    mark_comments_loaded(conn, req.notification_id)
    return FetchCommentsResult(notification_id=req.notification_id, comment_count=len(db_comments))


async def _handle_preload(
    req: PreLoadCommentsRequest,
    conn: sqlite3.Connection,
    token: str,
) -> PreLoadComplete:
    """Pre-load comments for top N notifications by priority."""
    nids = get_unloaded_top_notification_ids(conn, req.top_n)

    sem = asyncio.Semaphore(COMMENT_CONCURRENCY)
    loaded: list[str] = []

    async def _load(nid: str) -> None:
        async with sem:
            result = await _handle_fetch_comments(
                FetchCommentsRequest(notification_id=nid), conn, token
            )
            if result.comment_count > 0:
                loaded.append(nid)

    await asyncio.gather(*[_load(nid) for nid in nids])
    return PreLoadComplete(loaded_ids=tuple(loaded))


def _get_pr_ref(conn: sqlite3.Connection, notification_id: str) -> PRRef | None:
    """Extract PRRef from a notification's subject_url."""
    notif = get_notification(conn, notification_id)
    if notif is None or notif.subject_url is None:
        return None
    parsed = parse_subject_url(notif.subject_url)
    if parsed is None:
        return None
    return PRRef(owner=parsed.owner, repo=parsed.repo, number=parsed.number)


async def _handle_fetch_pr_detail(
    req: FetchPRDetailRequest,
    conn: sqlite3.Connection,
    token: str,
) -> FetchPRDetailResult:
    """Fetch full PR data: metadata, review threads, and changed files."""
    pr = _get_pr_ref(conn, req.notification_id)
    if pr is None:
        return FetchPRDetailResult(
            notification_id=req.notification_id,
            success=False,
            error="Cannot resolve PR from notification",
        )

    # Clear stale cache
    delete_pr_data_for_notification(conn, req.notification_id)

    # Fetch all three data sources
    metadata = await fetch_pr_metadata(token, pr.owner, pr.repo, pr.number)
    metadata["notification_id"] = req.notification_id
    upsert_pr_details(conn, metadata)

    comments, reviews = await fetch_review_threads(token, pr.owner, pr.repo, pr.number)
    upsert_pr_reviews(
        conn,
        [{**r, "notification_id": req.notification_id} for r in reviews],
    )
    for c in comments:
        c["notification_id"] = req.notification_id
        c["review_id"] = None
        c.setdefault("side", "RIGHT")
        c.setdefault("in_reply_to_id", None)
    upsert_review_comments(conn, comments)

    files = await fetch_pr_files(token, pr.owner, pr.repo, pr.number)
    upsert_pr_files(
        conn,
        [{**f, "notification_id": req.notification_id} for f in files],
    )

    return FetchPRDetailResult(notification_id=req.notification_id, success=True)


async def _handle_post_review_comment(
    req: PostReviewCommentRequest,
    conn: sqlite3.Connection,
    token: str,
) -> PostReviewCommentResult:
    """Post a reply to a review thread."""
    pr = _get_pr_ref(conn, req.notification_id)
    if pr is None:
        return PostReviewCommentResult(
            notification_id=req.notification_id,
            success=False,
            error="Cannot resolve PR from notification",
        )
    await post_review_reply(token, pr, req.comment_id, req.body)
    return PostReviewCommentResult(notification_id=req.notification_id, success=True)


async def _handle_submit_review(
    req: SubmitReviewRequest,
    conn: sqlite3.Connection,
    token: str,
) -> SubmitReviewResult:
    """Submit a PR review (approve or request changes)."""
    pr = _get_pr_ref(conn, req.notification_id)
    if pr is None:
        return SubmitReviewResult(
            notification_id=req.notification_id,
            success=False,
            error="Cannot resolve PR from notification",
        )
    await submit_review(token, pr, req.event, req.body)
    return SubmitReviewResult(notification_id=req.notification_id, success=True)


async def _handle_resolve_thread(
    req: ResolveThreadRequest,
    conn: sqlite3.Connection,
    token: str,
) -> ResolveThreadResult:
    """Resolve or unresolve a review thread."""
    _ = conn  # not needed for the mutation itself
    if req.resolve:
        await resolve_review_thread(token, req.thread_node_id)
    else:
        await unresolve_review_thread(token, req.thread_node_id)
    return ResolveThreadResult(notification_id=req.notification_id, success=True)


async def backend_worker(
    request_queue: asyncio.Queue[Request],
    response_queue: asyncio.Queue[Response],
    conn: sqlite3.Connection,
    token: str,
) -> None:
    """Process requests from the TUI and post results back."""
    while True:
        req = await request_queue.get()
        try:
            result: Response
            if isinstance(req, MarkDoneRequest):
                result = await _handle_mark_done(req, conn, token)
            elif isinstance(req, FetchCommentsRequest):
                result = await _handle_fetch_comments(req, conn, token)
            elif isinstance(req, PreLoadCommentsRequest):
                result = await _handle_preload(req, conn, token)
            elif isinstance(req, FetchPRDetailRequest):
                result = await _handle_fetch_pr_detail(req, conn, token)
            elif isinstance(req, PostReviewCommentRequest):
                result = await _handle_post_review_comment(req, conn, token)
            elif isinstance(req, SubmitReviewRequest):
                result = await _handle_submit_review(req, conn, token)
            elif isinstance(req, ResolveThreadRequest):
                result = await _handle_resolve_thread(req, conn, token)
            else:
                result = ErrorResult(request_type=type(req).__name__, error="Unknown request type")
            await response_queue.put(result)
        except Exception as e:  # noqa: BLE001
            await response_queue.put(ErrorResult(request_type=type(req).__name__, error=str(e)))
        finally:
            request_queue.task_done()
