"""Integration tests for the backend worker."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from forge_triage.backend import backend_worker
from forge_triage.db import get_notification, upsert_notification
from forge_triage.messages import (
    ErrorResult,
    FetchCommentsRequest,
    FetchCommentsResult,
    MarkDoneRequest,
    MarkDoneResult,
    PreLoadCommentsRequest,
    PreLoadComplete,
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

    req_q: asyncio.Queue[MarkDoneRequest | FetchCommentsRequest | PreLoadCommentsRequest] = (
        asyncio.Queue()
    )
    resp_q: asyncio.Queue[MarkDoneResult | FetchCommentsResult | PreLoadComplete | ErrorResult] = (
        asyncio.Queue()
    )

    task = asyncio.create_task(backend_worker(req_q, resp_q, tmp_db, "ghp_test"))

    await req_q.put(MarkDoneRequest(notification_ids=["1001"]))
    result = await asyncio.wait_for(resp_q.get(), timeout=5)

    assert isinstance(result, MarkDoneResult)
    assert result.notification_ids == ["1001"]
    assert result.errors == []

    # Verify notification deleted from DB
    assert get_notification(tmp_db, "1001") is None

    task.cancel()
