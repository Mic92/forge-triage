"""Integration tests for the GitHub API client."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from forge_triage.github import (
    AuthError,
    _validate_graphql_identifier,
    fetch_notifications,
    fetch_subject_details,
    get_github_token,
)

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
        url="https://api.github.com/notifications?per_page=50",
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


# ---------- fetch_subject_details ----------

# Notifications spanning two repos, all subject types + states
_NOTIFS_FOR_GRAPHQL = [
    {
        "id": "n1",
        "subject": {
            "type": "PullRequest",
            "url": "https://api.github.com/repos/NixOS/nixpkgs/pulls/100",
        },
    },
    {
        "id": "n2",
        "subject": {
            "type": "PullRequest",
            "url": "https://api.github.com/repos/NixOS/nixpkgs/pulls/200",
        },
    },
    {
        "id": "n3",
        "subject": {
            "type": "PullRequest",
            "url": "https://api.github.com/repos/NixOS/nixpkgs/pulls/300",
        },
    },
    {
        "id": "n4",
        "subject": {
            "type": "Issue",
            "url": "https://api.github.com/repos/other/repo/issues/10",
        },
    },
    {
        "id": "n5",
        "subject": {
            "type": "Issue",
            "url": "https://api.github.com/repos/other/repo/issues/20",
        },
    },
    # Null URL — should be excluded from GraphQL
    {
        "id": "n6",
        "subject": {
            "type": "Discussion",
            "url": None,
        },
    },
]

_GRAPHQL_RESPONSE = {
    "data": {
        "r0": {
            "pr_n1": {
                "state": "OPEN",
                "merged": False,
                "commits": {"nodes": [{"commit": {"statusCheckRollup": {"state": "SUCCESS"}}}]},
            },
            "pr_n2": {
                "state": "CLOSED",
                "merged": True,
                "commits": {"nodes": [{"commit": {"statusCheckRollup": {"state": "SUCCESS"}}}]},
            },
            "pr_n3": {
                "state": "CLOSED",
                "merged": False,
                "commits": {"nodes": [{"commit": {"statusCheckRollup": {"state": "FAILURE"}}}]},
            },
        },
        "r1": {
            "issue_n4": {"state": "OPEN"},
            "issue_n5": {"state": "CLOSED"},
        },
    }
}


async def test_fetch_subject_details(httpx_mock: HTTPXMock) -> None:
    """Batch GraphQL fetch: open/merged/closed PR, open/closed issue, null URL excluded."""
    httpx_mock.add_response(
        url="https://api.github.com/graphql",
        json=_GRAPHQL_RESPONSE,
    )

    result = await fetch_subject_details("ghp_test", _NOTIFS_FOR_GRAPHQL)

    assert result["n1"] == ("open", "success")
    assert result["n2"] == ("merged", "success")
    assert result["n3"] == ("closed", "failure")
    assert result["n4"] == ("open", None)
    assert result["n5"] == ("closed", None)
    # n6 (null URL) should not be in results at all
    assert "n6" not in result


async def test_fetch_subject_details_partial_error(httpx_mock: HTTPXMock) -> None:
    """GraphQL returns null for a node (e.g. deleted PR) → (None, None)."""
    notifs = [
        {
            "id": "ok1",
            "subject": {
                "type": "Issue",
                "url": "https://api.github.com/repos/a/b/issues/1",
            },
        },
        {
            "id": "bad1",
            "subject": {
                "type": "PullRequest",
                "url": "https://api.github.com/repos/a/b/pulls/999",
            },
        },
    ]
    httpx_mock.add_response(
        url="https://api.github.com/graphql",
        json={
            "data": {
                "r0": {
                    "issue_ok1": {"state": "OPEN"},
                    "pr_bad1": None,  # deleted / no access
                },
            }
        },
    )

    result = await fetch_subject_details("ghp_test", notifs)

    assert result["ok1"] == ("open", None)
    assert result["bad1"] == (None, None)


# ---------- get_github_token ----------


def test_get_github_token_raises_auth_error_when_gh_missing() -> None:
    """get_github_token raises AuthError (not FileNotFoundError) when gh CLI is absent."""
    with (
        patch("forge_triage.github.subprocess.run", side_effect=FileNotFoundError),
        pytest.raises(AuthError, match="not found"),
    ):
        get_github_token()


# ---------- GraphQL identifier validation ----------


def test_validate_graphql_identifier_rejects_injection() -> None:
    """Strings with GraphQL-breaking characters are rejected."""
    with pytest.raises(ValueError, match="Invalid GraphQL identifier"):
        _validate_graphql_identifier('evil") { __schema { types { name } } }')
    with pytest.raises(ValueError, match="Invalid GraphQL identifier"):
        _validate_graphql_identifier("name with spaces")
    with pytest.raises(ValueError, match="Invalid GraphQL identifier"):
        _validate_graphql_identifier("")
