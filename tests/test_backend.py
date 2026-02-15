"""Integration tests for the backend worker."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from forge_triage.backend import backend_worker
from forge_triage.db import get_comments, get_notification, upsert_notification
from forge_triage.messages import (
    MarkDoneRequest,
    MarkDoneResult,
    Request,
    Response,
)
from tests.conftest import NotificationRow

if TYPE_CHECKING:
    import sqlite3

    from pytest_httpx import HTTPXMock


async def test_mark_done_through_worker(tmp_db: sqlite3.Connection, httpx_mock: HTTPXMock) -> None:
    """Post MarkDoneRequest → backend calls API, deletes from DB, posts result."""
    upsert_notification(tmp_db, NotificationRow().as_dict())

    httpx_mock.add_response(
        url="https://api.github.com/notifications/threads/1001",
        method="PATCH",
        status_code=205,
        headers={"X-RateLimit-Remaining": "4990"},
    )

    req_q: asyncio.Queue[Request] = asyncio.Queue()
    resp_q: asyncio.Queue[Response] = asyncio.Queue()

    task = asyncio.create_task(backend_worker(req_q, resp_q, tmp_db, "ghp_test"))

    await req_q.put(MarkDoneRequest(notification_ids=["1001"]))
    result = await asyncio.wait_for(resp_q.get(), timeout=5)

    assert isinstance(result, MarkDoneResult)
    assert result.notification_ids == ["1001"]
    assert result.errors == []

    # Verify notification deleted from DB
    assert get_notification(tmp_db, "1001") is None

    task.cancel()


async def test_fetch_comments_deleted_user(
    tmp_db: sqlite3.Connection,
    httpx_mock: HTTPXMock,
) -> None:
    """REST comments with null user (deleted account) don't crash — author becomes '[deleted]'."""
    upsert_notification(tmp_db, NotificationRow().as_dict())

    httpx_mock.add_response(
        url="https://api.github.com/repos/NixOS/nixpkgs/issues/12345/comments",
        json=[
            {
                "id": 11111,
                "user": None,
                "body": "Ghost comment",
                "created_at": "2026-02-09T06:00:00Z",
                "updated_at": "2026-02-09T06:00:00Z",
            },
            {
                "id": 22222,
                "user": {"login": "alive-user"},
                "body": "Normal comment",
                "created_at": "2026-02-09T07:00:00Z",
                "updated_at": "2026-02-09T07:00:00Z",
            },
        ],
        headers={"X-RateLimit-Remaining": "4990"},
    )

    req_q: asyncio.Queue[Request] = asyncio.Queue()
    resp_q: asyncio.Queue[Response] = asyncio.Queue()

    task = asyncio.create_task(backend_worker(req_q, resp_q, tmp_db, "ghp_test"))

    await req_q.put(FetchCommentsRequest(notification_id="1001"))
    result = await asyncio.wait_for(resp_q.get(), timeout=5)

    assert isinstance(result, FetchCommentsResult)
    assert result.comment_count == 2

    comments = get_comments(tmp_db, "1001")
    authors = {c.author for c in comments}
    assert "[deleted]" in authors
    assert "alive-user" in authors

    task.cancel()
