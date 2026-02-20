"""Shared fixtures: temporary SQLite database, sample API JSON, mock helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest

from forge_triage.db import open_memory_db

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Generator


SAMPLE_NOTIFICATION_JSON = {
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

SAMPLE_COMMENT_JSON = {
    "id": 99999,
    "user": {"login": "contributor"},
    "body": "Ready for review — all tests pass.",
    "created_at": "2026-02-09T06:55:00Z",
    "updated_at": "2026-02-09T06:55:00Z",
}


@dataclass
class NotificationRow:
    """Builder for notification DB rows with sensible defaults."""

    notification_id: str = "1001"
    repo_owner: str = "NixOS"
    repo_name: str = "nixpkgs"
    subject_type: str = "PullRequest"
    subject_title: str = "python313: 3.13.1 -> 3.13.2"
    subject_url: str = "https://api.github.com/repos/NixOS/nixpkgs/pulls/12345"
    html_url: str = "https://github.com/NixOS/nixpkgs/pull/12345"
    reason: str = "review_requested"
    updated_at: str = "2026-02-09T07:00:00Z"
    unread: int = 1
    priority_score: int = 0
    priority_tier: str = "fyi"
    ci_status: str | None = None
    subject_state: str | None = None
    comments_loaded: int = 0
    last_viewed_at: str | None = None
    raw_json: str = field(default="")

    def __post_init__(self) -> None:
        if not self.raw_json:
            raw = dict(SAMPLE_NOTIFICATION_JSON)
            raw["id"] = self.notification_id
            raw["reason"] = self.reason
            raw["updated_at"] = self.updated_at
            self.raw_json = json.dumps(raw)

    def as_dict(self) -> dict[str, str | int | None]:
        """Return a dict suitable for DB insertion."""
        return {
            "notification_id": self.notification_id,
            "repo_owner": self.repo_owner,
            "repo_name": self.repo_name,
            "subject_type": self.subject_type,
            "subject_title": self.subject_title,
            "subject_url": self.subject_url,
            "html_url": self.html_url,
            "reason": self.reason,
            "updated_at": self.updated_at,
            "unread": self.unread,
            "priority_score": self.priority_score,
            "priority_tier": self.priority_tier,
            "raw_json": self.raw_json,
            "comments_loaded": self.comments_loaded,
            "last_viewed_at": self.last_viewed_at,
            "ci_status": self.ci_status,
            "subject_state": self.subject_state,
        }


@pytest.fixture
def tmp_db() -> Generator[sqlite3.Connection]:
    """Create an in-memory SQLite database with the full schema."""
    conn = open_memory_db()
    try:
        yield conn
    finally:
        conn.close()
