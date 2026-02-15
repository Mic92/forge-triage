"""Tests for the GitHub PR API client (reviews, files, mutations)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from forge_triage.github_pr import (
    fetch_pr_files,
    fetch_review_threads,
    parse_pr_metadata_response,
    parse_review_threads_response,
    resolve_review_thread,
)

if TYPE_CHECKING:
    from pytest_httpx import HTTPXMock


# --- Canned responses ---

GRAPHQL_PR_METADATA_RESPONSE = {
    "data": {
        "repository": {
            "pullRequest": {
                "number": 12345,
                "author": {"login": "contributor"},
                "body": "This PR updates python 3.13.1 to 3.13.2",
                "labels": {"nodes": [{"name": "python"}, {"name": "update"}]},
                "baseRefName": "main",
                "headRefName": "python-update",
            }
        }
    }
}

GRAPHQL_REVIEW_THREADS_RESPONSE = {
    "data": {
        "repository": {
            "pullRequest": {
                "reviewThreads": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "nodes": [
                        {
                            "id": "thread-1",
                            "isResolved": False,
                            "comments": {
                                "nodes": [
                                    {
                                        "id": "rc1",
                                        "author": {"login": "reviewer1"},
                                        "body": "This needs a docstring",
                                        "path": "src/main.py",
                                        "diffHunk": "@@ -10,6 +10,8 @@",
                                        "line": 15,
                                        "createdAt": "2026-02-09T08:00:00Z",
                                        "updatedAt": "2026-02-09T08:00:00Z",
                                    },
                                    {
                                        "id": "rc2",
                                        "author": {"login": "author1"},
                                        "body": "Done, added a docstring",
                                        "path": "src/main.py",
                                        "diffHunk": "@@ -10,6 +10,8 @@",
                                        "line": 15,
                                        "createdAt": "2026-02-09T09:00:00Z",
                                        "updatedAt": "2026-02-09T09:00:00Z",
                                    },
                                ]
                            },
                        },
                        {
                            "id": "thread-2",
                            "isResolved": True,
                            "comments": {
                                "nodes": [
                                    {
                                        "id": "rc3",
                                        "author": {"login": "reviewer2"},
                                        "body": "Typo here",
                                        "path": "README.md",
                                        "diffHunk": "@@ -1,3 +1,5 @@",
                                        "line": 3,
                                        "createdAt": "2026-02-09T07:00:00Z",
                                        "updatedAt": "2026-02-09T07:00:00Z",
                                    }
                                ]
                            },
                        },
                    ],
                },
                "reviews": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "nodes": [
                        {
                            "id": "rev1",
                            "author": {"login": "reviewer1"},
                            "state": "CHANGES_REQUESTED",
                            "body": "Please address the comments",
                            "submittedAt": "2026-02-09T08:00:00Z",
                        },
                        {
                            "id": "rev2",
                            "author": {"login": "reviewer2"},
                            "state": "APPROVED",
                            "body": "",
                            "submittedAt": "2026-02-09T10:00:00Z",
                        },
                    ],
                },
            }
        }
    }
}


# --- Parser tests (real logic) ---


def test_parse_pr_metadata_response() -> None:
    """Parse PR metadata: extracts author, labels list→JSON, refs."""
    result = parse_pr_metadata_response(GRAPHQL_PR_METADATA_RESPONSE)
    assert result["pr_number"] == 12345
    assert result["author"] == "contributor"
    assert result["body"] == "This PR updates python 3.13.1 to 3.13.2"
    assert result["labels_json"] == '["python", "update"]'
    assert result["base_ref"] == "main"
    assert result["head_ref"] == "python-update"


def test_parse_review_threads_response() -> None:
    """Parse review threads: flattens comments, maps isResolved→int, extracts reviews."""
    threads, reviews, has_next, cursor = parse_review_threads_response(
        GRAPHQL_REVIEW_THREADS_RESPONSE
    )

    # 3 comments across 2 threads, flattened
    assert len(threads) == 3
    assert threads[0]["comment_id"] == "rc1"
    assert threads[0]["thread_id"] == "thread-1"
    assert threads[0]["is_resolved"] == 0

    # rc2 inherits thread-1's metadata
    assert threads[1]["comment_id"] == "rc2"
    assert threads[1]["thread_id"] == "thread-1"

    # rc3 in resolved thread
    assert threads[2]["comment_id"] == "rc3"
    assert threads[2]["is_resolved"] == 1

    assert len(reviews) == 2
    assert reviews[0]["review_id"] == "rev1"
    assert reviews[0]["state"] == "CHANGES_REQUESTED"
    assert reviews[1]["state"] == "APPROVED"

    assert has_next is False
    assert cursor is None


def test_parse_null_author_deleted_account() -> None:
    """GraphQL returns author: null for deleted accounts — all parsers must handle it."""
    metadata_response: dict[str, object] = {
        "data": {
            "repository": {
                "pullRequest": {
                    "number": 99,
                    "author": None,
                    "body": "ghost PR",
                    "labels": {"nodes": []},
                    "baseRefName": "main",
                    "headRefName": "fix",
                }
            }
        }
    }
    assert parse_pr_metadata_response(metadata_response)["author"] == "[deleted]"

    threads_response: dict[str, object] = {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [
                            {
                                "id": "thread-ghost",
                                "isResolved": False,
                                "comments": {
                                    "nodes": [
                                        {
                                            "id": "rc-ghost",
                                            "author": None,
                                            "body": "I am a ghost",
                                            "path": "file.py",
                                            "diffHunk": "@@",
                                            "line": 1,
                                            "createdAt": "2026-01-01T00:00:00Z",
                                            "updatedAt": "2026-01-01T00:00:00Z",
                                        }
                                    ]
                                },
                            }
                        ],
                    },
                    "reviews": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [
                            {
                                "id": "rev-ghost",
                                "author": None,
                                "state": "COMMENTED",
                                "body": "",
                                "submittedAt": "2026-01-01T00:00:00Z",
                            }
                        ],
                    },
                }
            }
        }
    }
    comments, reviews, _, _ = parse_review_threads_response(threads_response)
    assert comments[0]["author"] == "[deleted]"
    assert reviews[0]["author"] == "[deleted]"


# --- Integration tests (real control flow) ---


async def test_fetch_pr_files_handles_missing_patch(httpx_mock: HTTPXMock) -> None:
    """Binary files with no patch key get None; normal files get their patch."""
    httpx_mock.add_response(
        url="https://api.github.com/repos/NixOS/nixpkgs/pulls/12345/files",
        json=[
            {
                "sha": "abc",
                "filename": "src/main.py",
                "status": "modified",
                "additions": 10,
                "deletions": 3,
                "patch": "@@ -1,5 +1,12 @@\n+import sys\n",
            },
            {
                "sha": "def",
                "filename": "image.png",
                "status": "added",
                "additions": 0,
                "deletions": 0,
                # no "patch" key — binary file
            },
        ],
        headers={"X-RateLimit-Remaining": "4999"},
    )
    files = await fetch_pr_files("ghp_test", "NixOS", "nixpkgs", 12345)
    assert len(files) == 2
    assert files[0]["patch"] == "@@ -1,5 +1,12 @@\n+import sys\n"
    assert files[1]["patch"] is None


async def test_fetch_review_threads_pagination(httpx_mock: HTTPXMock) -> None:
    """Cursor-based pagination: follows hasNextPage across two GraphQL requests."""
    page1 = {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "pageInfo": {"hasNextPage": True, "endCursor": "cursor-abc"},
                        "nodes": [
                            {
                                "id": "t1",
                                "isResolved": False,
                                "comments": {
                                    "nodes": [
                                        {
                                            "id": "c1",
                                            "author": {"login": "a"},
                                            "body": "First",
                                            "path": "f.py",
                                            "diffHunk": "@@",
                                            "line": 1,
                                            "createdAt": "2026-01-01T00:00:00Z",
                                            "updatedAt": "2026-01-01T00:00:00Z",
                                        }
                                    ]
                                },
                            }
                        ],
                    },
                    "reviews": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [],
                    },
                }
            }
        }
    }
    page2 = {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [
                            {
                                "id": "t2",
                                "isResolved": True,
                                "comments": {
                                    "nodes": [
                                        {
                                            "id": "c2",
                                            "author": {"login": "b"},
                                            "body": "Second",
                                            "path": "g.py",
                                            "diffHunk": "@@",
                                            "line": 5,
                                            "createdAt": "2026-01-02T00:00:00Z",
                                            "updatedAt": "2026-01-02T00:00:00Z",
                                        }
                                    ]
                                },
                            }
                        ],
                    },
                    "reviews": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [],
                    },
                }
            }
        }
    }
    httpx_mock.add_response(url="https://api.github.com/graphql", json=page1)
    httpx_mock.add_response(url="https://api.github.com/graphql", json=page2)

    threads, _reviews = await fetch_review_threads("ghp_test", "NixOS", "nixpkgs", 12345)
    assert len(threads) == 2
    assert threads[0]["comment_id"] == "c1"
    assert threads[1]["comment_id"] == "c2"
    assert threads[1]["is_resolved"] == 1


# --- Mutation error handling tests ---


async def test_resolve_thread_returns_false_on_graphql_errors(httpx_mock: HTTPXMock) -> None:
    """resolve_review_thread returns False when GraphQL response contains errors."""
    httpx_mock.add_response(
        url="https://api.github.com/graphql",
        json={
            "data": None,
            "errors": [{"message": "Could not resolve to a node with ID 'bad-id'"}],
        },
    )
    result = await resolve_review_thread("ghp_test", "bad-id")
    assert result is False



