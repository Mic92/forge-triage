"""Integration tests for the sync orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from forge_triage.db import (
    get_notification,
    get_notification_count,
    upsert_notification,
)
from forge_triage.sync import sync
from tests.conftest import NotificationRow

if TYPE_CHECKING:
    import sqlite3

    from pytest_httpx import HTTPXMock

NOTIFICATION_PR = {
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

NOTIFICATION_ISSUE = {
    "id": "1002",
    "repository": {
        "full_name": "other/repo",
        "owner": {"login": "other"},
        "name": "repo",
    },
    "subject": {
        "type": "Issue",
        "title": "Bug report",
        "url": "https://api.github.com/repos/other/repo/issues/42",
        "latest_comment_url": None,
    },
    "reason": "mention",
    "updated_at": "2026-02-09T06:00:00Z",
    "unread": True,
    "url": "https://api.github.com/notifications/threads/1002",
}

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

NOTIFICATION_CHECKSUITE = {
    "id": "3001",
    "repository": {
        "full_name": "Mic92/dotfiles",
        "owner": {"login": "Mic92"},
        "name": "dotfiles",
    },
    "subject": {
        "type": "CheckSuite",
        "title": "Update Flake Inputs workflow run failed for main branch",
        "url": None,
        "latest_comment_url": None,
    },
    "reason": "ci_activity",
    "updated_at": "2026-02-09T09:00:00Z",
    "unread": True,
    "url": "https://api.github.com/notifications/threads/3001",
}

NOTIFICATION_RELEASE = {
    "id": "3002",
    "repository": {
        "full_name": "cheat/cheat",
        "owner": {"login": "cheat"},
        "name": "cheat",
    },
    "subject": {
        "type": "Release",
        "title": "5.1.0",
        "url": "https://api.github.com/repos/cheat/cheat/releases/286633434",
        "latest_comment_url": "https://api.github.com/repos/cheat/cheat/releases/286633434",
    },
    "reason": "subscribed",
    "updated_at": "2026-02-09T09:30:00Z",
    "unread": True,
    "url": "https://api.github.com/notifications/threads/3002",
}


def _stub_rate_limit() -> dict[str, str]:
    return {"X-RateLimit-Remaining": "4900"}


def _graphql_response(data: dict[str, Any]) -> dict[str, Any]:
    return {"data": data}


async def test_initial_sync(tmp_db: sqlite3.Connection, httpx_mock: HTTPXMock) -> None:
    """Full initial sync: fetch → GraphQL details → priority → pre-load comments."""
    httpx_mock.add_response(
        url="https://api.github.com/notifications?per_page=50",
        json=[NOTIFICATION_PR],
        headers=_stub_rate_limit(),
    )
    httpx_mock.add_response(
        url="https://api.github.com/graphql",
        json=_graphql_response(
            {
                "r0": {
                    "pr_1001": {
                        "state": "OPEN",
                        "merged": False,
                        "commits": {
                            "nodes": [{"commit": {"statusCheckRollup": {"state": "SUCCESS"}}}]
                        },
                    },
                },
            }
        ),
    )
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

    row = get_notification(tmp_db, "1001")
    assert row is not None
    assert row.priority_score == 1000
    assert row.ci_status == "success"
    assert row.subject_state == "open"
    assert row.comments_loaded == 1


async def test_sync_mixed_notifications(tmp_db: sqlite3.Connection, httpx_mock: HTTPXMock) -> None:
    """Sync with merged PR + closed issue + null-URL discussion + CheckSuite + Release."""
    httpx_mock.add_response(
        url="https://api.github.com/notifications?per_page=50",
        json=[
            NOTIFICATION_PR,
            NOTIFICATION_ISSUE,
            NOTIFICATION_NULL_SUBJECT_URL,
            NOTIFICATION_CHECKSUITE,
            NOTIFICATION_RELEASE,
        ],
        headers=_stub_rate_limit(),
    )
    httpx_mock.add_response(
        url="https://api.github.com/graphql",
        json=_graphql_response(
            {
                "r0": {
                    "pr_1001": {
                        "state": "CLOSED",
                        "merged": True,
                        "commits": {
                            "nodes": [{"commit": {"statusCheckRollup": {"state": "SUCCESS"}}}]
                        },
                    },
                },
                "r1": {
                    "issue_1002": {"state": "CLOSED"},
                },
            }
        ),
    )
    httpx_mock.add_response(
        url="https://api.github.com/repos/NixOS/nixpkgs/issues/12345/comments",
        json=[],
        headers=_stub_rate_limit(),
    )
    httpx_mock.add_response(
        url="https://api.github.com/repos/other/repo/issues/42/comments",
        json=[],
        headers=_stub_rate_limit(),
    )

    result = await sync(tmp_db, "ghp_test")

    assert result.new == 5
    assert result.total == 5

    pr = get_notification(tmp_db, "1001")
    assert pr is not None
    assert pr.subject_state == "merged"
    assert pr.ci_status == "success"
    assert pr.html_url == "https://github.com/NixOS/nixpkgs/pull/12345"

    issue = get_notification(tmp_db, "1002")
    assert issue is not None
    assert issue.subject_state == "closed"
    assert issue.ci_status is None
    assert issue.html_url == "https://github.com/other/repo/issues/42"

    disc = get_notification(tmp_db, "2001")
    assert disc is not None
    assert disc.subject_state is None
    assert disc.subject_url is None
    assert disc.html_url == "https://github.com/NixOS/nixpkgs"

    # CheckSuite: null subject URL should get actions page fallback
    checksuite = get_notification(tmp_db, "3001")
    assert checksuite is not None
    assert checksuite.subject_url is None
    assert checksuite.html_url == "https://github.com/Mic92/dotfiles/actions"

    # Release: numeric API ID should become /releases/tag/<title>
    release = get_notification(tmp_db, "3002")
    assert release is not None
    assert release.html_url == "https://github.com/cheat/cheat/releases/tag/5.1.0"


async def test_purge_stale_notifications(tmp_db: sqlite3.Connection, httpx_mock: HTTPXMock) -> None:
    """Stale notifications older than the oldest returned are purged; newer ones kept."""
    # Pre-populate 5 notifications with varying timestamps
    for i, ts in enumerate(
        [
            "2026-02-01T00:00:00Z",
            "2026-02-02T00:00:00Z",
            "2026-02-03T00:00:00Z",
            "2026-02-04T00:00:00Z",
            "2026-02-05T00:00:00Z",
        ]
    ):
        upsert_notification(
            tmp_db,
            NotificationRow(
                notification_id=str(5000 + i),
                updated_at=ts,
            ).as_dict(),
        )
    assert get_notification_count(tmp_db) == 5

    # Sync returns only 3 notifications (IDs 5001, 5002, 5003) with oldest = Feb 2
    # Notifications 5000 (Feb 1) should be purged (older than cutoff)
    # Notification 5004 (Feb 5) should be kept (newer than cutoff, just unchanged)
    returned = []
    for nid, ts in [
        ("5001", "2026-02-02T00:00:00Z"),
        ("5002", "2026-02-03T00:00:00Z"),
        ("5003", "2026-02-04T00:00:00Z"),
    ]:
        n = {**NOTIFICATION_PR, "id": nid, "updated_at": ts}
        returned.append(n)

    httpx_mock.add_response(
        url="https://api.github.com/notifications?per_page=50",
        json=returned,
        headers=_stub_rate_limit(),
    )
    httpx_mock.add_response(
        url="https://api.github.com/graphql",
        json=_graphql_response(
            {
                "r0": {
                    f"pr_{nid}": {
                        "state": "OPEN",
                        "merged": False,
                        "commits": {"nodes": [{"commit": {"statusCheckRollup": None}}]},
                    }
                    for nid in ["5001", "5002", "5003"]
                },
            }
        ),
    )
    # Comment preload for up to 4 surviving notifications (all share same subject URL)
    for _ in range(4):
        httpx_mock.add_response(
            url="https://api.github.com/repos/NixOS/nixpkgs/issues/12345/comments",
            json=[],
            headers=_stub_rate_limit(),
        )

    result = await sync(tmp_db, "ghp_test")

    assert result.purged == 1  # only 5000 purged
    # 5000 gone (older than cutoff)
    assert get_notification(tmp_db, "5000") is None
    # 5004 kept (newer than cutoff)
    assert get_notification(tmp_db, "5004") is not None
    assert result.total == 4  # 3 returned + 1 kept


async def test_sync_paginates_and_caps_at_max(
    tmp_db: sqlite3.Connection, httpx_mock: HTTPXMock
) -> None:
    """Sync follows pagination links and stops once max_notifications is reached.

    With max_notifications=2 and two pages of 1 notification each, sync should
    fetch both pages and stop without requesting a third.
    """
    page1_notif = {**NOTIFICATION_PR, "id": "6001", "updated_at": "2026-02-09T07:00:00Z"}
    page2_notif = {**NOTIFICATION_PR, "id": "6002", "updated_at": "2026-02-09T08:00:00Z"}

    httpx_mock.add_response(
        url="https://api.github.com/notifications?per_page=50",
        json=[page1_notif],
        headers={
            **_stub_rate_limit(),
            "Link": '<https://api.github.com/notifications?page=2>; rel="next"',
        },
    )
    httpx_mock.add_response(
        url="https://api.github.com/notifications?page=2",
        json=[page2_notif],
        headers={
            **_stub_rate_limit(),
            # There would be a page 3, but sync should stop after hitting max
            "Link": '<https://api.github.com/notifications?page=3>; rel="next"',
        },
    )
    # page 3 is NOT mocked — if sync requests it, the test fails
    httpx_mock.add_response(
        url="https://api.github.com/graphql",
        json=_graphql_response(
            {
                "r0": {
                    f"pr_{nid}": {
                        "state": "OPEN",
                        "merged": False,
                        "commits": {"nodes": [{"commit": {"statusCheckRollup": None}}]},
                    }
                    for nid in ["6001", "6002"]
                },
            }
        ),
    )
    httpx_mock.add_response(
        url="https://api.github.com/repos/NixOS/nixpkgs/issues/12345/comments",
        json=[],
        headers=_stub_rate_limit(),
    )
    httpx_mock.add_response(
        url="https://api.github.com/repos/NixOS/nixpkgs/issues/12345/comments",
        json=[],
        headers=_stub_rate_limit(),
    )

    result = await sync(tmp_db, "ghp_test", max_notifications=2)

    assert result.new == 2
    assert result.total == 2
    assert get_notification(tmp_db, "6001") is not None
    assert get_notification(tmp_db, "6002") is not None


async def test_purge_all_on_empty_sync(tmp_db: sqlite3.Connection, httpx_mock: HTTPXMock) -> None:
    """Empty sync response purges all local notifications."""
    upsert_notification(tmp_db, NotificationRow(notification_id="9001").as_dict())
    upsert_notification(tmp_db, NotificationRow(notification_id="9002").as_dict())
    assert get_notification_count(tmp_db) == 2

    httpx_mock.add_response(
        url="https://api.github.com/notifications?per_page=50",
        json=[],
        headers=_stub_rate_limit(),
    )

    result = await sync(tmp_db, "ghp_test")

    assert result.purged == 2
    assert result.total == 0
