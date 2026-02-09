"""Integration tests for the sync orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from forge_triage.db import get_sync_meta
from forge_triage.sync import _notification_to_row, sync

if TYPE_CHECKING:
    import sqlite3

    from pytest_httpx import HTTPXMock

NOTIFICATION_1 = {
    "id": "1001",
    "repository": {
        "full_name": "NixOS/nixpkgs",
        "owner": {"login": "NixOS"},
        "name": "nixpkgs",
    },
    "subject": {
        "type": "PullRequest",
        "title": "python313: 3.13.1 -> 3.13.2",
        "url": "https://api.github.com/repos/NixOS/nixpkgs/pulls/12345",
        "latest_comment_url": "https://api.github.com/repos/NixOS/nixpkgs/issues/comments/99999",
    },
    "reason": "review_requested",
    "updated_at": "2026-02-09T07:00:00Z",
    "unread": True,
    "url": "https://api.github.com/notifications/threads/1001",
}


def _stub_rate_limit() -> dict[str, str]:
    return {"X-RateLimit-Remaining": "4900"}


def _mock_pr_and_ci(httpx_mock: HTTPXMock, pr_url: str, ci_state: str) -> None:
    """Register mock responses for PR detail + CI status."""
    httpx_mock.add_response(
        url=pr_url,
        json={"head": {"sha": "abc123"}},
        headers=_stub_rate_limit(),
    )
    httpx_mock.add_response(
        url="https://api.github.com/repos/NixOS/nixpkgs/commits/abc123/status",
        json={"state": ci_state, "total_count": 3},
        headers=_stub_rate_limit(),
    )


async def test_initial_sync(tmp_db: sqlite3.Connection, httpx_mock: HTTPXMock) -> None:
    """Full initial sync: fetch → upsert → CI → priority → pre-load comments."""
    # Mock notifications endpoint
    httpx_mock.add_response(
        url="https://api.github.com/notifications",
        json=[NOTIFICATION_1],
        headers=_stub_rate_limit(),
    )
    # Mock PR + CI status
    _mock_pr_and_ci(
        httpx_mock,
        "https://api.github.com/repos/NixOS/nixpkgs/pulls/12345",
        "success",
    )
    # Mock comments pre-load
    httpx_mock.add_response(
        url="https://api.github.com/repos/NixOS/nixpkgs/issues/12345/comments",
        json=[
            {
                "id": 99999,
                "user": {"login": "alice"},
                "body": "LGTM",
                "created_at": "2026-02-09T06:55:00Z",
                "updated_at": "2026-02-09T06:55:00Z",
            }
        ],
        headers=_stub_rate_limit(),
    )

    result = await sync(tmp_db, "ghp_test")

    assert result.new == 1
    assert result.updated == 0
    assert result.total == 1

    # Verify DB state
    row = tmp_db.execute("SELECT * FROM notifications WHERE notification_id = '1001'").fetchone()
    assert row is not None
    assert row["priority_score"] == 1000  # review_requested + CI success
    assert row["priority_tier"] == "blocking"
    assert row["ci_status"] == "success"
    assert row["comments_loaded"] == 1

    # Verify comments were pre-loaded
    comments = tmp_db.execute("SELECT * FROM comments WHERE notification_id = '1001'").fetchall()
    assert len(comments) == 1
    assert comments[0]["author"] == "alice"

    # Verify sync metadata updated
    assert get_sync_meta(tmp_db, "last_sync_at") == "2026-02-09T07:00:00Z"


# Regression: GitHub API can return subject.url as null (e.g. Discussion, CheckSuite)
NOTIFICATION_NULL_SUBJECT_URL = {
    "id": "2001",
    "repository": {
        "full_name": "NixOS/nixpkgs",
        "owner": {"login": "NixOS"},
        "name": "nixpkgs",
    },
    "subject": {
        "type": "Discussion",
        "title": "RFC: something interesting",
        "url": None,
        "latest_comment_url": None,
    },
    "reason": "subscribed",
    "updated_at": "2026-02-09T08:00:00Z",
    "unread": True,
    "url": "https://api.github.com/notifications/threads/2001",
}


def test_notification_to_row_null_subject_url() -> None:
    """_notification_to_row must handle subject.url being None."""
    row = _notification_to_row(
        NOTIFICATION_NULL_SUBJECT_URL,
        ci_status=None,
        priority_score=100,
        priority_tier="fyi",
    )
    assert row["notification_id"] == "2001"
    assert row["subject_url"] is None
    assert row["html_url"] is None


async def test_sync_null_subject_url(tmp_db: sqlite3.Connection, httpx_mock: HTTPXMock) -> None:
    """Full sync must not crash on notifications with null subject URL."""
    httpx_mock.add_response(
        url="https://api.github.com/notifications",
        json=[NOTIFICATION_NULL_SUBJECT_URL],
        headers=_stub_rate_limit(),
    )

    result = await sync(tmp_db, "ghp_test")

    assert result.new == 1
    assert result.total == 1
    row = tmp_db.execute("SELECT * FROM notifications WHERE notification_id = '2001'").fetchone()
    assert row is not None
    assert row["subject_url"] is None
    assert row["html_url"] is None


async def test_sync_respects_max_notifications(
    tmp_db: sqlite3.Connection, httpx_mock: HTTPXMock
) -> None:
    """Sync stops fetching after max_notifications is reached."""
    # Return 3 notifications but set limit to 2
    notifs = []
    for i in range(3):
        n = dict(NOTIFICATION_1)
        n["id"] = str(3001 + i)
        n["updated_at"] = f"2026-02-09T0{7 + i}:00:00Z"
        notifs.append(n)

    httpx_mock.add_response(
        url="https://api.github.com/notifications",
        json=notifs,
        headers=_stub_rate_limit(),
    )
    # Mock PR + CI for 2 notifications (only 2 will be processed)
    for _ in range(2):
        _mock_pr_and_ci(
            httpx_mock,
            "https://api.github.com/repos/NixOS/nixpkgs/pulls/12345",
            "success",
        )
    # Mock comments pre-load
    for _ in range(2):
        httpx_mock.add_response(
            url="https://api.github.com/repos/NixOS/nixpkgs/issues/12345/comments",
            json=[],
            headers=_stub_rate_limit(),
        )

    result = await sync(tmp_db, "ghp_test", max_notifications=2)

    assert result.new == 2
    assert result.total == 2


async def test_sync_progress_callback(tmp_db: sqlite3.Connection, httpx_mock: HTTPXMock) -> None:
    """Sync calls the progress callback as it processes notifications."""
    httpx_mock.add_response(
        url="https://api.github.com/notifications",
        json=[NOTIFICATION_1],
        headers=_stub_rate_limit(),
    )
    _mock_pr_and_ci(
        httpx_mock,
        "https://api.github.com/repos/NixOS/nixpkgs/pulls/12345",
        "success",
    )
    httpx_mock.add_response(
        url="https://api.github.com/repos/NixOS/nixpkgs/issues/12345/comments",
        json=[],
        headers=_stub_rate_limit(),
    )

    progress_calls: list[tuple[int, int]] = []

    def on_progress(current: int, total: int) -> None:
        progress_calls.append((current, total))

    await sync(tmp_db, "ghp_test", on_progress=on_progress)

    # Should have been called once (1 notification processed)
    assert len(progress_calls) == 1
    assert progress_calls[0] == (1, 1)
