"""Integration tests for the TUI."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from forge_triage.config import UserCommand
from forge_triage.db import upsert_notification
from forge_triage.messages import MarkDoneRequest, Request
from forge_triage.tui.app import TriageApp
from forge_triage.tui.detail_pane import DetailPane
from forge_triage.tui.notification_list import NotificationList, _state_icon
from forge_triage.tui.widgets.command_palette import CommandPalette
from tests.conftest import NotificationRow

if TYPE_CHECKING:
    import sqlite3


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
            # PR url → title rendered as **[#12345](url) Fix critical bug**
            html_url="https://github.com/NixOS/nixpkgs/pull/12345",
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
    # Plain URL (no PR/issue number) → title rendered as **[Discuss architecture](url)**
    upsert_notification(
        conn,
        NotificationRow(
            notification_id="1004",
            subject_title="Discuss architecture",
            reason="subscribed",
            priority_score=50,
            priority_tier="fyi",
            html_url="https://github.com/NixOS/nixpkgs/discussions/42",
        ).as_dict(),
    )
    # No URL → title rendered as **Commit note**
    upsert_notification(
        conn,
        NotificationRow(
            notification_id="1005",
            subject_title="Commit note",
            reason="subscribed",
            priority_score=10,
            priority_tier="fyi",
            html_url="",
        ).as_dict(),
    )


async def test_tui_shows_notifications(tmp_db: sqlite3.Connection) -> None:
    """TUI launches and displays notifications from the DB."""
    _populate_db(tmp_db)

    app = TriageApp(conn=tmp_db)
    async with app.run_test():
        nlist = app.query_one(NotificationList)
        assert nlist.row_count == 5
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
    req_q: asyncio.Queue[Request] = asyncio.Queue()
    app = TriageApp(conn=tmp_db, request_queue=req_q)

    async with app.run_test() as pilot:
        nlist = app.query_one(NotificationList)
        assert nlist.selected_notification_id == "1001"

        # Drain any startup requests (e.g. FetchCommentsRequest from on_mount)
        while not req_q.empty():
            req_q.get_nowait()

        await pilot.press("d")
        await pilot.pause()
        assert nlist.row_count == 4
        req = req_q.get_nowait()
        assert isinstance(req, MarkDoneRequest)
        assert req.notification_ids == ("1001",)


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
    """Detail pane updates when the cursor moves to a different notification.

    Also covers the three title-rendering branches added in _format_title:
    - PR/issue URL  → **[#NNN](url) Title**
    - plain URL     → **[Title](url)**
    - no URL        → **Title**
    """
    _populate_db(tmp_db)
    app = TriageApp(conn=tmp_db)

    async with app.run_test() as pilot:
        detail = app.query_one(DetailPane)

        # Row 1 (1001): PR url → **[#12345](url) Fix critical bug**
        assert "[#12345](https://github.com/NixOS/nixpkgs/pull/12345)" in detail.source
        assert "Fix critical bug" in detail.source

        # Move down to second notification
        await pilot.press("j")
        await pilot.pause()
        assert "Add new feature" in detail.source

        # Move down again to third notification
        await pilot.press("j")
        await pilot.pause()
        assert "Update docs" in detail.source

        # Row 4 (1004): plain URL (discussion) → **[Discuss architecture](url)**
        await pilot.press("j")
        await pilot.pause()
        assert (
            "[Discuss architecture](https://github.com/NixOS/nixpkgs/discussions/42)"
            in detail.source
        )

        # Row 5 (1005): no URL → **Commit note**
        await pilot.press("j")
        await pilot.pause()
        assert "**Commit note**" in detail.source
        assert "](http" not in detail.source


async def test_refresh_reloads_from_db(tmp_db: sqlite3.Connection) -> None:
    """Pressing r refreshes the notification list from the database."""
    _populate_db(tmp_db)
    app = TriageApp(conn=tmp_db)

    async with app.run_test() as pilot:
        nlist = app.query_one(NotificationList)
        assert nlist.row_count == 5

        # Insert a new notification directly into the DB (simulating a background sync)
        upsert_notification(
            tmp_db,
            NotificationRow(
                notification_id="1006",
                subject_title="New hotfix",
                reason="assign",
                priority_score=900,
                priority_tier="blocking",
            ).as_dict(),
        )

        # List still shows 5 until we refresh
        assert nlist.row_count == 5

        await pilot.press("r")
        await pilot.pause()
        assert nlist.row_count == 6


async def test_quit(tmp_db: sqlite3.Connection) -> None:
    """Pressing q exits the TUI."""
    _populate_db(tmp_db)
    app = TriageApp(conn=tmp_db)
    async with app.run_test() as pilot:
        await pilot.press("q")


def test_state_icon_mapping() -> None:
    """Verify nerdfont icons for all subject type + state combinations."""
    assert _state_icon("Issue", "open").plain == "\uf41b"
    assert _state_icon("Issue", "open").style == "green"

    assert _state_icon("Issue", "closed").plain == "\uf41d"
    assert _state_icon("Issue", "closed").style == "purple"

    assert _state_icon("PullRequest", "open").plain == "\uf407"
    assert _state_icon("PullRequest", "open").style == "green"

    assert _state_icon("PullRequest", "merged").plain == "\uf419"
    assert _state_icon("PullRequest", "merged").style == "purple"

    assert _state_icon("PullRequest", "closed").plain == "\uf4dc"
    assert _state_icon("PullRequest", "closed").style == "red"

    assert _state_icon("Discussion", None).plain == "\uf49a"
    assert _state_icon("Discussion", None).style == "dim"

    assert _state_icon(None, None).plain == "\uf49a"


def _populate_pr_notification(conn: sqlite3.Connection) -> None:
    """Insert a single PR notification."""
    upsert_notification(
        conn,
        NotificationRow(
            notification_id="2001",
            subject_type="PullRequest",
            subject_title="Fix the thing",
            reason="review_requested",
            priority_score=1000,
            priority_tier="blocking",
        ).as_dict(),
    )


def _populate_issue_notification(conn: sqlite3.Connection) -> None:
    """Insert a single Issue notification."""
    upsert_notification(
        conn,
        NotificationRow(
            notification_id="3001",
            subject_type="Issue",
            subject_title="Bug report",
            reason="mention",
            priority_score=500,
            priority_tier="action",
        ).as_dict(),
    )


async def test_main_list_palette_opens_for_pr(tmp_db: sqlite3.Connection) -> None:
    """Pressing `:` on a PR in the main list → CommandPalette pushed with user commands."""
    _populate_pr_notification(tmp_db)
    user_commands = [
        UserCommand(
            name="Checkout", args=["gh", "pr", "checkout", "{pr_number}"], mode="foreground"
        ),
    ]

    app = TriageApp(conn=tmp_db, user_commands=user_commands)
    async with app.run_test(size=(120, 40)) as pilot:
        nlist = app.query_one(NotificationList)
        assert nlist.selected_notification_id == "2001"

        await pilot.press("colon")
        await pilot.pause()

        assert isinstance(app.screen, CommandPalette)
        assert "Checkout" in app.screen.action_labels


async def test_main_list_palette_non_pr_shows_notify(tmp_db: sqlite3.Connection) -> None:
    """Pressing `:` on a non-PR notification → notify shown, no palette pushed."""
    _populate_issue_notification(tmp_db)

    app = TriageApp(
        conn=tmp_db,
        user_commands=[
            UserCommand(name="Checkout", args=["gh", "pr", "checkout"], mode="foreground"),
        ],
    )
    async with app.run_test(size=(120, 40)) as pilot:
        nlist = app.query_one(NotificationList)
        assert nlist.selected_notification_id == "3001"

        await pilot.press("colon")
        await pilot.pause()

        # Should stay on main screen — no palette pushed
        assert not isinstance(app.screen, CommandPalette)


async def test_main_list_palette_no_commands_shows_notify(tmp_db: sqlite3.Connection) -> None:
    """Pressing `:` on a PR with no user commands → notify shown, no palette pushed."""
    _populate_pr_notification(tmp_db)

    app = TriageApp(conn=tmp_db, user_commands=[])
    async with app.run_test(size=(120, 40)) as pilot:
        nlist = app.query_one(NotificationList)
        assert nlist.selected_notification_id == "2001"

        await pilot.press("colon")
        await pilot.pause()

        assert not isinstance(app.screen, CommandPalette)
