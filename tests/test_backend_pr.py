"""Integration tests for PR-specific backend handlers."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from forge_triage.backend import backend_worker
from forge_triage.db import upsert_notification
from forge_triage.messages import (
    FetchPRDetailRequest,
    FetchPRDetailResult,
)
from forge_triage.pr_db import get_pr_details, get_pr_files, get_review_threads
from tests.conftest import NotificationRow

if TYPE_CHECKING:
    import sqlite3

    from pytest_httpx import HTTPXMock

from forge_triage.messages import Request, Response

# Canned API responses matching the real GitHub API shape

_GRAPHQL_METADATA = {
    "data": {
        "repository": {
            "pullRequest": {
                "number": 12345,
                "author": {"login": "contributor"},
                "body": "Update python",
                "labels": {"nodes": [{"name": "python"}]},
                "baseRefName": "main",
                "headRefName": "python-update",
            }
        }
    }
}

_GRAPHQL_THREADS = {
    "data": {
        "repository": {
            "pullRequest": {
                "reviewThreads": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "nodes": [
                        {
                            "id": "t1",
                            "isResolved": False,
                            "comments": {
                                "nodes": [
                                    {
                                        "id": "rc1",
                                        "author": {"login": "reviewer"},
                                        "body": "Needs work",
                                        "path": "src/main.py",
                                        "diffHunk": "@@",
                                        "line": 10,
                                        "createdAt": "2026-02-09T08:00:00Z",
                                        "updatedAt": "2026-02-09T08:00:00Z",
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
                            "id": "rev1",
                            "author": {"login": "reviewer"},
                            "state": "COMMENTED",
                            "body": "",
                            "submittedAt": "2026-02-09T08:00:00Z",
                        }
                    ],
                },
            }
        }
    }
}

_REST_FILES = [
    {
        "sha": "abc",
        "filename": "src/main.py",
        "status": "modified",
        "additions": 5,
        "deletions": 2,
        "patch": "@@ -1 +1 @@\n-old\n+new",
    },
]


async def test_fetch_pr_detail_stores_all_data(
    tmp_db: sqlite3.Connection,
    httpx_mock: HTTPXMock,
) -> None:
    """FetchPRDetailRequest fetches metadata+threads+files from API and caches in DB."""
    upsert_notification(tmp_db, NotificationRow().as_dict())

    # Mock: 2 GraphQL calls (metadata, then threads) + 1 REST call (files)
    httpx_mock.add_response(url="https://api.github.com/graphql", json=_GRAPHQL_METADATA)
    httpx_mock.add_response(url="https://api.github.com/graphql", json=_GRAPHQL_THREADS)
    httpx_mock.add_response(
        url="https://api.github.com/repos/NixOS/nixpkgs/pulls/12345/files",
        json=_REST_FILES,
        headers={"X-RateLimit-Remaining": "4999"},
    )

    req_q: asyncio.Queue[Request] = asyncio.Queue()
    resp_q: asyncio.Queue[Response] = asyncio.Queue()

    task = asyncio.create_task(backend_worker(req_q, resp_q, tmp_db, "ghp_test"))

    await req_q.put(FetchPRDetailRequest(notification_id="1001"))
    result = await asyncio.wait_for(resp_q.get(), timeout=5)

    assert isinstance(result, FetchPRDetailResult)
    assert result.success is True

    # Verify data stored in DB
    details = get_pr_details(tmp_db, "1001")
    assert details is not None
    assert details.author == "contributor"
    assert details.pr_number == 12345

    threads = get_review_threads(tmp_db, "1001")
    assert len(threads) == 1
    assert threads[0].body == "Needs work"

    files = get_pr_files(tmp_db, "1001")
    assert len(files) == 1
    assert files[0].filename == "src/main.py"

    task.cancel()
