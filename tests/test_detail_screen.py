"""Tests for the DetailScreen and context-aware keybindings."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.containers import VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Input, Markdown, Static, TabbedContent

from forge_triage.db import upsert_notification
from forge_triage.pr_db import upsert_pr_details, upsert_pr_reviews, upsert_review_comments
from forge_triage.tui.app import TriageApp
from forge_triage.tui.detail_screen import DetailScreen
from forge_triage.tui.help_screen import HelpScreen
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


async def test_pr_detail_has_two_tabs(tmp_db: sqlite3.Connection) -> None:
    """PR detail view has 2 tabs (Conversation, Files Changed), Conversation active by default.

    The Conversation tab renders PR metadata (title, author, branch, labels)
    followed by description body followed by review threads in chronological order.
    """
    _seed_pr_notification(tmp_db)

    app = TriageApp(conn=tmp_db)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("enter")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, DetailScreen)

        tabs = screen.query_one(TabbedContent)
        # Should have exactly 2 tab panes
        panes = list(tabs.query("TabPane"))
        assert len(panes) == 2

        # Conversation tab should be active by default
        assert tabs.active == "tab-conversation"

        # Conversation tab should contain merged content
        conversation_md = screen.query_one("#conversation-content", Markdown)
        source = conversation_md.source

        # PR metadata
        assert "python313: 3.13.1 -> 3.13.2" in source
        assert "contributor" in source
        assert "python-update" in source
        assert "`python`" in source

        # Description body
        assert "Update python 3.13" in source

        # Review threads (should appear after description)
        assert "src/main.py" in source
        assert "Needs a docstring" in source

        # Verify ordering: description before review thread
        desc_pos = source.index("Update python 3.13")
        thread_pos = source.index("Needs a docstring")
        assert desc_pos < thread_pos


async def test_conversation_tab_edge_cases(tmp_db: sqlite3.Connection) -> None:
    """Edge cases: no description, no labels, no review threads."""
    # PR with no description, no labels, no review threads
    upsert_notification(tmp_db, NotificationRow().as_dict())
    upsert_pr_details(
        tmp_db,
        {
            "notification_id": "1001",
            "pr_number": 1,
            "author": "contributor",
            "body": "",
            "labels_json": "[]",
            "base_ref": "main",
            "head_ref": "fix",
        },
    )

    app = TriageApp(conn=tmp_db)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("enter")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, DetailScreen)

        conversation_md = screen.query_one("#conversation-content", Markdown)
        source = conversation_md.source

        # No description shows placeholder
        assert "No description provided." in source

        # No labels => no "Labels:" line
        assert "Labels:" not in source

        # No review threads => placeholder
        assert "No conversations yet." in source


async def test_tab_switching_all_methods(tmp_db: sqlite3.Connection) -> None:
    """Test all tab switching methods: 1/2, Tab/Shift+Tab, h/l."""
    _seed_pr_notification(tmp_db)

    app = TriageApp(conn=tmp_db)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("enter")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, DetailScreen)
        tabs = screen.query_one(TabbedContent)

        # Start on Conversation (tab 1)
        assert tabs.active == "tab-conversation"

        # Number keys: 2 -> Files Changed
        await pilot.press("2")
        await pilot.pause()
        assert tabs.active == "tab-files"

        # Number keys: 1 -> Conversation
        await pilot.press("1")
        await pilot.pause()
        assert tabs.active == "tab-conversation"

        # Tab cycles forward: Conversation -> Files Changed
        await pilot.press("tab")
        await pilot.pause()
        assert tabs.active == "tab-files"

        # Tab wraps: Files Changed -> Conversation
        await pilot.press("tab")
        await pilot.pause()
        assert tabs.active == "tab-conversation"

        # Shift+Tab cycles backward: Conversation -> Files Changed (wraps)
        await pilot.press("shift+tab")
        await pilot.pause()
        assert tabs.active == "tab-files"

        # Shift+Tab: Files Changed -> Conversation
        await pilot.press("shift+tab")
        await pilot.pause()
        assert tabs.active == "tab-conversation"

        # l switches right: Conversation -> Files Changed
        await pilot.press("l")
        await pilot.pause()
        assert tabs.active == "tab-files"

        # h switches left: Files Changed -> Conversation
        await pilot.press("h")
        await pilot.pause()
        assert tabs.active == "tab-conversation"


def _seed_long_content_pr(conn: sqlite3.Connection) -> None:
    """Insert a PR notification with very long description for scroll testing."""
    upsert_notification(conn, NotificationRow().as_dict())
    long_body = "\n\n".join(f"Paragraph {i}: " + "x " * 50 for i in range(100))
    upsert_pr_details(
        conn,
        {
            "notification_id": "1001",
            "pr_number": 1,
            "author": "contributor",
            "body": long_body,
            "labels_json": "[]",
            "base_ref": "main",
            "head_ref": "fix",
        },
    )


async def test_vim_scroll_all_keys(tmp_db: sqlite3.Connection) -> None:
    """Vim-style scrolling: j/k/G/End/g/Home/Ctrl+d/Ctrl+u."""
    _seed_long_content_pr(tmp_db)

    app = TriageApp(conn=tmp_db)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("enter")
        await pilot.pause()
        # Give time for Markdown to render and be scrollable
        await pilot.pause()
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, DetailScreen)

        # Find the active VerticalScroll
        vs = screen.query_one("#tab-conversation VerticalScroll", VerticalScroll)

        # Should start at top
        assert vs.scroll_y == 0

        # j scrolls down
        await pilot.press("j")
        await pilot.pause()
        assert vs.scroll_y > 0
        scroll_after_j = vs.scroll_y

        # k scrolls up
        await pilot.press("k")
        await pilot.pause()
        assert vs.scroll_y < scroll_after_j

        # G jumps to bottom
        await pilot.press("G")
        await pilot.pause()
        scroll_at_bottom = vs.scroll_y
        assert scroll_at_bottom > 0

        # g jumps to top
        await pilot.press("g")
        await pilot.pause()
        assert vs.scroll_y == 0

        # End jumps to bottom
        await pilot.press("end")
        await pilot.pause()
        assert vs.scroll_y == scroll_at_bottom

        # Home jumps to top
        await pilot.press("home")
        await pilot.pause()
        assert vs.scroll_y == 0

        # Ctrl+d scrolls down roughly half viewport
        await pilot.press("ctrl+d")
        await pilot.pause()
        scroll_after_half = vs.scroll_y
        assert scroll_after_half > 0

        # Ctrl+u scrolls back up roughly half viewport
        await pilot.press("ctrl+u")
        await pilot.pause()
        assert vs.scroll_y < scroll_after_half


async def test_scroll_boundary_behavior(tmp_db: sqlite3.Connection) -> None:
    """Scroll boundary: j at bottom, k at top, Ctrl+d near bottom doesn't overshoot."""
    _seed_long_content_pr(tmp_db)

    app = TriageApp(conn=tmp_db)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, DetailScreen)

        vs = screen.query_one("#tab-conversation VerticalScroll", VerticalScroll)

        # k at top doesn't change scroll_y
        assert vs.scroll_y == 0
        await pilot.press("k")
        await pilot.pause()
        assert vs.scroll_y == 0

        # G to bottom, then j doesn't change
        await pilot.press("G")
        await pilot.pause()
        bottom = vs.scroll_y
        await pilot.press("j")
        await pilot.pause()
        assert vs.scroll_y == bottom

        # Go near bottom, Ctrl+d lands at max (no overshoot)
        await pilot.press("g")
        await pilot.pause()
        await pilot.press("G")
        await pilot.pause()
        # Scroll up a tiny bit from bottom
        await pilot.press("k")
        await pilot.pause()
        near_bottom = vs.scroll_y
        await pilot.press("ctrl+d")
        await pilot.pause()
        assert vs.scroll_y >= near_bottom  # Should be at or near bottom


async def test_search_basic_flow(tmp_db: sqlite3.Connection) -> None:
    """/  shows search input, Enter submits, scrolls to match, hides input."""
    _seed_pr_notification(tmp_db)

    app = TriageApp(conn=tmp_db)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("enter")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, DetailScreen)

        search_input = screen.query_one("#search-input", Input)

        # Search input should be hidden initially
        assert not search_input.display

        # / shows search input
        await pilot.press("slash")
        await pilot.pause()
        assert search_input.display
        assert search_input.has_focus

        # Type query and press Enter — "docstring" appears in review thread
        await pilot.press("d", "o", "c", "s", "t", "r", "i", "n", "g")
        await pilot.press("enter")
        await pilot.pause()

        # Search input hides after submission
        assert not search_input.display

        # Now test no matches
        await pilot.press("slash")
        await pilot.pause()
        await pilot.press("z", "z", "z", "z", "z")
        await pilot.press("enter")
        await pilot.pause()

        # Should hide input even with no matches
        assert not search_input.display


async def test_search_navigation(tmp_db: sqlite3.Connection) -> None:
    """n/N navigate through multiple matches, wrapping."""
    # Create PR with multiple occurrences of "python"
    _seed_pr_notification(tmp_db)

    app = TriageApp(conn=tmp_db)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, DetailScreen)

        # Search for "python" — appears in title and labels
        await pilot.press("slash")
        await pilot.pause()
        await pilot.press("p", "y", "t", "h", "o", "n")
        await pilot.press("enter")
        await pilot.pause()

        # Should have matches
        assert len(screen.search_matches) >= 2

        first_idx = screen.search_index

        # n goes to next match
        await pilot.press("n")
        await pilot.pause()
        assert screen.search_index == first_idx + 1

        # Navigate to end and wrap
        for _ in range(len(screen.search_matches)):
            await pilot.press("n")
            await pilot.pause()

        # Should wrap back to 0
        assert screen.search_index == first_idx + 1  # wrapped around

        # N goes to previous
        await pilot.press("N")
        await pilot.pause()
        # Should be back at 0
        assert screen.search_index == 0


async def test_search_escape_behavior(tmp_db: sqlite3.Connection) -> None:
    """Escape clears search/hides input. Second Escape pops screen."""
    _seed_pr_notification(tmp_db)

    app = TriageApp(conn=tmp_db)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("enter")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, DetailScreen)

        search_input = screen.query_one("#search-input", Input)

        # Open search and type something
        await pilot.press("slash")
        await pilot.pause()

        # Escape while input focused hides input and clears search
        await pilot.press("escape")
        await pilot.pause()
        assert not search_input.display
        assert len(app.screen_stack) == 2  # Still on detail screen

        # Do a real search to create active search state
        await pilot.press("slash")
        await pilot.pause()
        await pilot.press("p", "y", "t", "h", "o", "n")
        await pilot.press("enter")
        await pilot.pause()

        # Now have active search, input not focused
        assert len(screen.search_matches) > 0
        assert not search_input.has_focus

        # First Escape clears search state, does NOT pop screen
        await pilot.press("escape")
        await pilot.pause()
        assert len(screen.search_matches) == 0
        assert len(app.screen_stack) == 2  # Still on detail screen

        # Second Escape pops the screen
        await pilot.press("escape")
        await pilot.pause()
        assert len(app.screen_stack) == 1


async def test_keys_type_into_search_input(tmp_db: sqlite3.Connection) -> None:
    """With search input focused, j/k/g/G/h/l type into input, not scroll/switch."""
    _seed_pr_notification(tmp_db)

    app = TriageApp(conn=tmp_db)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("enter")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, DetailScreen)

        search_input = screen.query_one("#search-input", Input)

        # Open search
        await pilot.press("slash")
        await pilot.pause()
        assert search_input.has_focus

        # Type chars that are also bound to actions
        await pilot.press("j", "k", "g", "G", "h", "l")
        await pilot.pause()

        # Should be typed into the input
        assert search_input.value == "jkgGhl"

        # Verify scroll didn't change
        vs = screen.query_one("#tab-conversation VerticalScroll", VerticalScroll)
        assert vs.scroll_y == 0

        # Verify tab didn't change
        tabs = screen.query_one(TabbedContent)
        assert tabs.active == "tab-conversation"


async def test_detail_help_shows_new_keybindings(tmp_db: sqlite3.Connection) -> None:
    """Help text shows updated keybindings, does NOT reference tab 3."""
    _seed_pr_notification(tmp_db)

    app = TriageApp(conn=tmp_db)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("enter")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, DetailScreen)

        # Open help
        await pilot.press("question_mark")
        await pilot.pause()

        help_screen = app.screen
        assert isinstance(help_screen, HelpScreen)

        help_static = help_screen.query_one(Static)
        text = str(help_static.render())

        # Should contain new keybindings
        for key in [
            "j",
            "k",
            "g",
            "G",
            "Home",
            "End",
            "Ctrl+d",
            "Ctrl+u",
            "Tab",
            "Shift+Tab",
            "h",
            "l",
            "/",
            "n",
            "N",
        ]:
            assert key in text, f"Expected '{key}' in help text"

        # Should NOT reference tab 3
        assert "3" not in text or "tab 3" not in text.lower()


async def test_conversation_tab_shows_diff_hunk(tmp_db: sqlite3.Connection) -> None:
    """Conversations tab shows the diff hunk as code context and omits null line numbers."""
    diff_hunk = "@@ -10,6 +10,8 @@\n checklist['eligible'] = true"
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
                "diff_hunk": diff_hunk,
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

        # Conversation is now tab 1 (active by default), no need to switch
        conversation = screen.query_one("#conversation-content", Markdown)
        assert "None" not in conversation.source
        assert "ci/merge.js" in conversation.source
        # Diff hunk should be rendered as a code block
        assert "checklist['eligible'] = true" in conversation.source
