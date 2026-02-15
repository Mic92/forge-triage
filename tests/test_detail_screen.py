"""Tests for the DetailScreen and context-aware keybindings."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.css.query import NoMatches
from textual.widgets import Markdown, TabbedContent

from forge_triage.db import upsert_notification
from forge_triage.pr_db import upsert_pr_details, upsert_pr_reviews, upsert_review_comments
from forge_triage.tui.app import TriageApp
from forge_triage.tui.detail_screen import DetailScreen
from tests.conftest import NotificationRow

if TYPE_CHECKING:
    import sqlite3


def _seed_pr_notification(conn: sqlite3.Connection) -> None:
    """Insert a PR notification with cached details for testing."""
    upsert_notification(conn, NotificationRow().as_dict())
    upsert_pr_details(
        conn,
        {
            "notification_id": "1001",
            "pr_number": 12345,
            "author": "contributor",
            "body": "Update python 3.13",
            "labels_json": '["python"]',
            "base_ref": "main",
            "head_ref": "python-update",
        },
    )
    upsert_pr_reviews(
        conn,
        [
            {
                "review_id": "r1",
                "notification_id": "1001",
                "author": "reviewer",
                "state": "COMMENTED",
                "body": "",
                "submitted_at": "2026-02-09T08:00:00Z",
            },
        ],
    )
    upsert_review_comments(
        conn,
        [
            {
                "comment_id": "rc1",
                "review_id": "r1",
                "notification_id": "1001",
                "thread_id": "t1",
                "author": "reviewer",
                "body": "Needs a docstring",
                "path": "src/main.py",
                "diff_hunk": "@@",
                "line": 10,
                "side": "RIGHT",
                "in_reply_to_id": None,
                "is_resolved": 0,
                "created_at": "2026-02-09T08:00:00Z",
                "updated_at": "2026-02-09T08:00:00Z",
            },
        ],
    )


def _seed_issue_notification(conn: sqlite3.Connection) -> None:
    """Insert an issue notification for testing."""
    upsert_notification(
        conn,
        NotificationRow(
            notification_id="2001",
            subject_type="Issue",
            subject_title="Bug report: crash on startup",
        ).as_dict(),
    )


async def test_enter_pushes_detail_screen_and_q_pops(tmp_db: sqlite3.Connection) -> None:
    """Enter on a notification pushes DetailScreen; q returns to the list."""
    _seed_pr_notification(tmp_db)

    app = TriageApp(conn=tmp_db)
    async with app.run_test(size=(120, 40)) as pilot:
        # Should start on main screen
        assert len(app.screen_stack) == 1

        # Press Enter to open detail
        await pilot.press("enter")
        await pilot.pause()

        assert len(app.screen_stack) == 2
        assert isinstance(app.screen, DetailScreen)

        # Press q to go back
        await pilot.press("q")
        await pilot.pause()

        assert len(app.screen_stack) == 1
        assert not isinstance(app.screen, DetailScreen)


async def test_detail_screen_shows_pr_tabs(tmp_db: sqlite3.Connection) -> None:
    """PR notifications get a tabbed view with Description, Conversations, Files Changed."""
    _seed_pr_notification(tmp_db)

    app = TriageApp(conn=tmp_db)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("enter")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, DetailScreen)

        # Verify tabs exist
        tabs = screen.query_one(TabbedContent)
        assert tabs is not None


async def test_detail_screen_shows_issue_without_tabs(tmp_db: sqlite3.Connection) -> None:
    """Issue notifications get a single scrollable view, no tabs."""
    _seed_issue_notification(tmp_db)

    app = TriageApp(conn=tmp_db)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("enter")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, DetailScreen)

        # Should NOT have TabbedContent
        try:
            screen.query_one(TabbedContent)
            has_tabs = True
        except NoMatches:
            has_tabs = False
        assert not has_tabs


async def test_conversation_tab_null_line(tmp_db: sqlite3.Connection) -> None:
    """Review comments with line=None must not show 'None' in the header."""
    upsert_notification(tmp_db, NotificationRow().as_dict())
    upsert_pr_details(
        tmp_db,
        {
            "notification_id": "1001",
            "pr_number": 1,
            "author": "a",
            "body": "",
            "labels_json": "[]",
            "base_ref": "main",
            "head_ref": "fix",
        },
    )
    upsert_pr_reviews(
        tmp_db,
        [
            {
                "review_id": "r1",
                "notification_id": "1001",
                "author": "reviewer",
                "state": "COMMENTED",
                "body": "",
                "submitted_at": "2026-01-01T00:00:00Z",
            },
        ],
    )
    upsert_review_comments(
        tmp_db,
        [
            {
                "comment_id": "rc1",
                "review_id": "r1",
                "notification_id": "1001",
                "thread_id": "t1",
                "author": "reviewer",
                "body": "file-level comment",
                "path": "ci/merge.js",
                "diff_hunk": "@@",
                "line": None,
                "side": "RIGHT",
                "in_reply_to_id": None,
                "is_resolved": True,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            },
        ],
    )

    app = TriageApp(conn=tmp_db)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("enter")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, DetailScreen)

        # Switch to Conversations tab
        await pilot.press("2")
        await pilot.pause()

        conversations = screen.query_one("#conversations-content", Markdown)
        assert "None" not in conversations.source
        assert "ci/merge.js" in conversations.source
