"""Integration tests for the GitHub API client."""

from __future__ import annotations

from typing import TYPE_CHECKING

from forge_triage.github import fetch_notifications

if TYPE_CHECKING:
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

NOTIFICATION_2 = {
    "id": "1002",
    "repository": {
        "full_name": "NixOS/nixpkgs",
        "owner": {"login": "NixOS"},
        "name": "nixpkgs",
    },
    "subject": {
        "type": "PullRequest",
        "title": "nixos-rebuild: fix switch",
        "url": "https://api.github.com/repos/NixOS/nixpkgs/pulls/67890",
        "latest_comment_url": "https://api.github.com/repos/NixOS/nixpkgs/issues/comments/88888",
    },
    "reason": "mention",
    "updated_at": "2026-02-09T06:00:00Z",
    "unread": True,
    "url": "https://api.github.com/notifications/threads/1002",
}


async def test_fetch_notifications_pagination(httpx_mock: HTTPXMock) -> None:
    """Follow Link header for pagination, accumulate results."""
    httpx_mock.add_response(
        url="https://api.github.com/notifications",
        json=[NOTIFICATION_1],
        headers={
            "Link": '<https://api.github.com/notifications?page=2>; rel="next"',
            "X-RateLimit-Remaining": "4998",
        },
    )
    httpx_mock.add_response(
        url="https://api.github.com/notifications?page=2",
        json=[NOTIFICATION_2],
        headers={"X-RateLimit-Remaining": "4997"},
    )
    result = await fetch_notifications("ghp_test")
    assert len(result) == 2
    assert result[0]["id"] == "1001"
    assert result[1]["id"] == "1002"
