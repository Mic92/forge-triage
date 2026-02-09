"""Integration tests for the TUI."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from forge_triage.db import upsert_notification
from forge_triage.messages import (
    FetchCommentsRequest,
    MarkDoneRequest,
    PreLoadCommentsRequest,
)
from forge_triage.tui.app import TriageApp
from forge_triage.tui.notification_list import NotificationList
from tests.conftest import NotificationRow

if TYPE_CHECKING:
    import sqlite3

type _Request = MarkDoneRequest | FetchCommentsRequest | PreLoadCommentsRequest


def _populate_db(conn: sqlite3.Connection) -> None:
    """Insert a few notifications for testing."""
    upsert_notification(
        conn,
        NotificationRow(
            notification_id="1001",
            subject_title="Fix critical bug",
            reason="review_requested",
            priority_score=1000,
            priority_tier="blocking",
        ).as_dict(),
    )
    upsert_notification(
        conn,
        NotificationRow(
            notification_id="1002",
            subject_title="Add new feature",
            reason="mention",
            priority_score=600,
            priority_tier="action",
        ).as_dict(),
    )
    upsert_notification(
        conn,
        NotificationRow(
            notification_id="1003",
            subject_title="Update docs",
            reason="subscribed",
            priority_score=100,
            priority_tier="fyi",
        ).as_dict(),
    )


async def test_tui_shows_notifications(tmp_db: sqlite3.Connection) -> None:
    """TUI launches and displays notifications from the DB."""
    _populate_db(tmp_db)

    app = TriageApp(conn=tmp_db)
    async with app.run_test():
        nlist = app.query_one(NotificationList)
        assert nlist.row_count == 3
        # First row should be highest priority
        assert nlist.selected_notification_id == "1001"


async def test_tui_empty_inbox(tmp_db: sqlite3.Connection) -> None:
    """TUI with empty DB shows inbox-empty message."""
    app = TriageApp(conn=tmp_db)
    async with app.run_test():
        empty_msg = app.query_one("#empty-message")
        rendered = empty_msg.render()
        assert hasattr(rendered, "plain")
        assert "empty" in rendered.plain.lower()


async def test_mark_done_posts_request(tmp_db: sqlite3.Connection) -> None:
    """Pressing d posts a MarkDoneRequest and removes from list."""
    _populate_db(tmp_db)
    req_q: asyncio.Queue[_Request] = asyncio.Queue()
    app = TriageApp(conn=tmp_db, request_queue=req_q)

    async with app.run_test() as pilot:
        nlist = app.query_one(NotificationList)
        assert nlist.selected_notification_id == "1001"

        # Drain any startup requests (e.g. FetchCommentsRequest from on_mount)
        while not req_q.empty():
            req_q.get_nowait()

        await pilot.press("d")
        await pilot.pause()
        assert nlist.row_count == 2
        req = req_q.get_nowait()
        assert isinstance(req, MarkDoneRequest)
        assert req.notification_ids == ["1001"]


async def test_vim_jk_navigation(tmp_db: sqlite3.Connection) -> None:
    """Pressing j/k moves cursor down/up like arrow keys."""
    _populate_db(tmp_db)
    app = TriageApp(conn=tmp_db)

    async with app.run_test() as pilot:
        nlist = app.query_one(NotificationList)
        # Starts on first row (highest priority)
        assert nlist.cursor_row == 0
        assert nlist.selected_notification_id == "1001"

        # j moves down
        await pilot.press("j")
        await pilot.pause()
        assert nlist.cursor_row == 1
        assert nlist.selected_notification_id == "1002"

        # j again moves to third row
        await pilot.press("j")
        await pilot.pause()
        assert nlist.cursor_row == 2
        assert nlist.selected_notification_id == "1003"

        # k moves back up
        await pilot.press("k")
        await pilot.pause()
        assert nlist.cursor_row == 1
        assert nlist.selected_notification_id == "1002"


async def test_detail_pane_updates_on_cursor_move(tmp_db: sqlite3.Connection) -> None:
    """Detail pane updates when the cursor moves to a different notification."""
    _populate_db(tmp_db)
    app = TriageApp(conn=tmp_db)

    async with app.run_test() as pilot:
        detail = app.query_one("#detail-pane")
        rendered = detail.render()
        assert hasattr(rendered, "plain")
        # Initially shows first notification
        assert "Fix critical bug" in rendered.plain

        # Move down to second notification
        await pilot.press("j")
        await pilot.pause()
        rendered = detail.render()
        assert hasattr(rendered, "plain")
        assert "Add new feature" in rendered.plain

        # Move down again to third notification
        await pilot.press("j")
        await pilot.pause()
        rendered = detail.render()
        assert hasattr(rendered, "plain")
        assert "Update docs" in rendered.plain


async def test_refresh_reloads_from_db(tmp_db: sqlite3.Connection) -> None:
    """Pressing r refreshes the notification list from the database."""
    _populate_db(tmp_db)
    app = TriageApp(conn=tmp_db)

    async with app.run_test() as pilot:
        nlist = app.query_one(NotificationList)
        assert nlist.row_count == 3

        # Insert a new notification directly into the DB (simulating a background sync)
        upsert_notification(
            tmp_db,
            NotificationRow(
                notification_id="1004",
                subject_title="New hotfix",
                reason="assign",
                priority_score=900,
                priority_tier="blocking",
            ).as_dict(),
        )

        # List still shows 3 until we refresh
        assert nlist.row_count == 3

        await pilot.press("r")
        await pilot.pause()
        assert nlist.row_count == 4


async def test_quit(tmp_db: sqlite3.Connection) -> None:
    """Pressing q exits the TUI."""
    _populate_db(tmp_db)
    app = TriageApp(conn=tmp_db)
    async with app.run_test() as pilot:
        await pilot.press("q")
