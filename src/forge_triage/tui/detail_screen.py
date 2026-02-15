"""Full-screen detail view for a notification, pushed as a Textual Screen."""

from __future__ import annotations

import json
import logging
import re
import webbrowser
from typing import TYPE_CHECKING, ClassVar

from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Markdown, Static, TabbedContent, TabPane

from forge_triage.db import Notification, get_comments, get_notification
from forge_triage.messages import FetchPRDetailRequest, MarkDoneRequest, SubmitReviewRequest
from forge_triage.pr_db import ReviewComment, get_pr_details, get_pr_files, get_review_threads
from forge_triage.tui.help_screen import HelpScreen
from forge_triage.tui.widgets.command_palette import CommandPalette

if TYPE_CHECKING:
    import asyncio
    import sqlite3

    from textual.app import ComposeResult
    from textual.binding import BindingType

    from forge_triage.messages import Request

logger = logging.getLogger(__name__)


def _build_meta_line(notif: Notification) -> str:
    """Build the metadata line (repo, type, reason, state, CI) for a notification."""
    meta_parts = [
        f"{notif.repo_owner}/{notif.repo_name}",
        notif.subject_type,
        notif.reason,
    ]
    if notif.subject_state:
        state_icons = {"open": "🟢", "closed": "🔴", "merged": "🟣"}
        icon = state_icons.get(notif.subject_state, "")
        meta_parts.append(f"{icon} {notif.subject_state}")
    if notif.ci_status:
        ci_icons = {"success": "✅", "failure": "❌", "pending": "⏳"}
        icon = ci_icons.get(notif.ci_status, "❓")
        meta_parts.append(f"**CI:** {icon} {notif.ci_status}")
    return "  •  ".join(meta_parts)


def _render_review_threads(threads: list[ReviewComment]) -> list[str]:
    """Render review threads into markdown lines."""
    if not threads:
        return ["*No conversations yet.*"]

    parts: list[str] = []
    thread_groups: dict[str | None, list[ReviewComment]] = {}
    for comment in threads:
        thread_groups.setdefault(comment.thread_id, []).append(comment)

    for comments in thread_groups.values():
        first = comments[0]
        resolved = " (Resolved)" if first.is_resolved else ""
        location = f"{first.path}:{first.line}" if first.line is not None else first.path
        parts.append(f"### `{location}`{resolved}")
        parts.append("")

        if first.diff_hunk:
            parts.append("```diff")
            parts.append(first.diff_hunk)
            parts.append("```")
            parts.append("")

        for c in comments:
            parts.append(f"**{c.author}** — {c.created_at}")
            parts.append("")
            parts.append(c.body)
            parts.append("")

        parts.append("---")
        parts.append("")

    return parts


class DetailScreen(Screen[None]):
    """Full-screen detail view for a notification.

    PRs get a tabbed layout (Description / Conversations / Files Changed).
    Issues and other types get a single scrollable view.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "go_back", "Back", show=True),
        Binding("escape", "go_back", "Back", show=False),
        Binding("r", "refresh_detail", "Refresh", show=True),
        Binding("question_mark", "show_help", "Help", show=True),
        Binding("o", "open_browser", "Open", show=True),
        Binding("d", "mark_done", "Done", show=True, priority=True),
        Binding("1", "tab_1", "Conversation", show=False),
        Binding("2", "tab_2", "Files", show=False),
        Binding("tab", "tab_next", "Next Tab", show=False),
        Binding("shift+tab", "tab_prev", "Prev Tab", show=False),
        Binding("h", "tab_prev", "Prev Tab", show=False),
        Binding("l", "tab_next", "Next Tab", show=False),
        Binding("j", "scroll_line_down", "Scroll Down", show=False),
        Binding("k", "scroll_line_up", "Scroll Up", show=False),
        Binding("g", "scroll_to_top", "Top", show=False),
        Binding("G", "scroll_to_bottom", "Bottom", show=False, key_display="G"),
        Binding("home", "scroll_to_top", "Top", show=False),
        Binding("end", "scroll_to_bottom", "Bottom", show=False),
        Binding("ctrl+d", "half_page_down", "Half Page Down", show=False),
        Binding("ctrl+u", "half_page_up", "Half Page Up", show=False),
        Binding("slash", "open_search", "Search", show=False),
        Binding("n", "search_next", "Next Match", show=False, priority=True),
        Binding("N", "search_prev", "Prev Match", show=False, key_display="N", priority=True),
        Binding("colon", "open_palette", "Actions", show=True),
        Binding("ctrl+p", "open_palette", "Actions", show=False),
    ]

    def __init__(
        self,
        conn: sqlite3.Connection,
        notification_id: str,
        request_queue: asyncio.Queue[Request] | None = None,
    ) -> None:
        super().__init__()
        self._conn = conn
        self._notification_id = notification_id
        self._request_queue = request_queue
        self._is_pr = False
        self.search_matches: list[int] = []  # line positions of matches
        self.search_index: int = 0

    DEFAULT_CSS = """
    #search-input {
        dock: bottom;
        display: none;
    }
    """

    def compose(self) -> ComposeResult:
        notif = get_notification(self._conn, self._notification_id)
        yield Header()
        if notif is None:
            yield Static("Notification not found.")
            yield Footer()
            return

        self._is_pr = notif.subject_type == "PullRequest"

        if self._is_pr:
            with TabbedContent("Conversation", "Files Changed", id="tabs"):
                with TabPane("Conversation", id="tab-conversation"):
                    yield VerticalScroll(Markdown(id="conversation-content"))
                with TabPane("Files Changed", id="tab-files"):
                    yield VerticalScroll(Static(id="files-content"))
        else:
            with VerticalScroll():
                yield Markdown(id="detail-content")

        yield Input(placeholder="Search…", id="search-input")
        yield Footer()

    def on_mount(self) -> None:
        """Load initial content and start background fetch for PRs."""
        self.refresh_content()
        if self._is_pr and self._request_queue is not None:
            self._request_queue.put_nowait(
                FetchPRDetailRequest(notification_id=self._notification_id)
            )

    def refresh_content(self) -> None:
        """Render content into the appropriate widgets."""
        notif = get_notification(self._conn, self._notification_id)
        if notif is None:
            return

        if self._is_pr:
            self._render_conversation_tab(notif)
            self._render_files_tab()
        else:
            self._render_issue_view(notif)

    def _render_conversation_tab(self, notif: Notification) -> None:
        """Render the combined Conversation tab: PR metadata + description + review threads."""
        parts: list[str] = []
        parts.append(f"# {notif.subject_title}")
        parts.append(_build_meta_line(notif))

        pr_details = get_pr_details(self._conn, self._notification_id)
        if pr_details is not None:
            parts.append(f"**Author:** {pr_details.author}")
            parts.append(f"**Branch:** {pr_details.head_ref} → {pr_details.base_ref}")

            try:
                labels: list[str] = json.loads(pr_details.labels_json)
            except (json.JSONDecodeError, TypeError):
                labels = []
            if labels:
                parts.append("**Labels:** " + ", ".join(f"`{lbl}`" for lbl in labels))

            parts.append("")
            parts.append("---")
            parts.append("")
            if pr_details.body:
                parts.append(pr_details.body)
            else:
                parts.append("*No description provided.*")
        else:
            parts.append("")
            parts.append("*⏳ Loading PR details…*")

        # Review threads
        parts.append("")
        parts.append("---")
        parts.append("")

        threads = get_review_threads(self._conn, self._notification_id)
        parts.extend(_render_review_threads(threads))

        self._update_markdown("#conversation-content", "\n".join(parts))

    def _render_files_tab(self) -> None:
        """Render the Files Changed tab with diff summaries."""
        files = get_pr_files(self._conn, self._notification_id)

        if not files:
            self._update_static(
                "#files-content",
                "[dim]⏳ Loading PR details…[/dim]",
            )
            return

        parts: list[str] = []
        for f in files:
            status_style = {"added": "green", "modified": "yellow", "removed": "red"}.get(
                f.status, ""
            )
            parts.append(
                f"[{status_style}]{f.status}[/{status_style}]  "
                f"[bold]{_escape(f.filename)}[/bold]  "
                f"[green]+{f.additions}[/green] [red]-{f.deletions}[/red]"
            )
            if f.patch:
                patch_lines = f.patch.split("\n")[:20]
                for line in patch_lines:
                    if line.startswith("+"):
                        parts.append(f"  [green]{_escape(line)}[/green]")
                    elif line.startswith("-"):
                        parts.append(f"  [red]{_escape(line)}[/red]")
                    else:
                        parts.append(f"  [dim]{_escape(line)}[/dim]")
            elif f.patch is None:
                parts.append("  [dim]Binary file — no diff available[/dim]")
            parts.append("")

        self._update_static("#files-content", "\n".join(parts))

    def _render_issue_view(self, notif: Notification) -> None:
        """Render a simple issue/other notification view."""
        parts: list[str] = []
        parts.append(f"# {notif.subject_title}")
        parts.append(_build_meta_line(notif))
        parts.append("")

        comments = get_comments(self._conn, self._notification_id)
        if comments:
            parts.append(f"## Comments ({len(comments)})")
            parts.append("")
            for c in comments:
                parts.append(f"**{c.author}** — {c.created_at}")
                parts.append("")
                parts.append(c.body)
                parts.append("")
        else:
            parts.append("*No comments.*")

        self._update_markdown("#detail-content", "\n".join(parts))

    def _update_markdown(self, widget_id: str, content: str) -> None:
        """Safely update a Markdown widget's content."""
        try:
            widget = self.query_one(widget_id, Markdown)
            widget.update(content)
        except NoMatches:
            logger.debug("Widget %s not found", widget_id)

    def _update_static(self, widget_id: str, content: str) -> None:
        """Safely update a Static widget's content."""
        try:
            widget = self.query_one(widget_id, Static)
            widget.update(content)
        except NoMatches:
            logger.debug("Widget %s not found", widget_id)

    # === Actions ===

    def action_refresh_detail(self) -> None:
        """Refresh PR data from the API."""
        if self._request_queue is not None:
            self._request_queue.put_nowait(
                FetchPRDetailRequest(notification_id=self._notification_id)
            )
            self.notify("Refreshing…")

    def action_open_browser(self) -> None:
        """Open the notification URL in the browser."""
        notif = get_notification(self._conn, self._notification_id)
        if notif is not None and notif.html_url:
            webbrowser.open(notif.html_url)

    def action_mark_done(self) -> None:
        """Mark this notification as done and go back."""
        if self._request_queue is not None:
            self._request_queue.put_nowait(
                MarkDoneRequest(notification_ids=(self._notification_id,))
            )
        self.app.pop_screen()

    def action_show_help(self) -> None:
        """Show help screen."""
        self.app.push_screen(HelpScreen(context="detail"))

    _TAB_IDS: ClassVar[list[str]] = ["tab-conversation", "tab-files"]

    def action_tab_1(self) -> None:
        """Switch to Conversation tab."""
        self._switch_tab("tab-conversation")

    def action_tab_2(self) -> None:
        """Switch to Files Changed tab."""
        self._switch_tab("tab-files")

    def action_tab_next(self) -> None:
        """Cycle to the next tab (wrapping)."""
        try:
            tabs = self.query_one(TabbedContent)
            current = tabs.active
            idx = self._TAB_IDS.index(current) if current in self._TAB_IDS else 0
            next_idx = (idx + 1) % len(self._TAB_IDS)
            tabs.active = self._TAB_IDS[next_idx]
            self._clear_search()
        except NoMatches:
            pass

    def action_tab_prev(self) -> None:
        """Cycle to the previous tab (wrapping)."""
        try:
            tabs = self.query_one(TabbedContent)
            current = tabs.active
            idx = self._TAB_IDS.index(current) if current in self._TAB_IDS else 0
            prev_idx = (idx - 1) % len(self._TAB_IDS)
            tabs.active = self._TAB_IDS[prev_idx]
            self._clear_search()
        except NoMatches:
            pass

    def _get_active_scroll(self) -> VerticalScroll | None:
        """Return the VerticalScroll in the active tab pane, or None."""
        try:
            tabs = self.query_one(TabbedContent)
            active_pane = tabs.query_one(f"#{tabs.active}", TabPane)
            return active_pane.query_one(VerticalScroll)
        except NoMatches:
            # Fall back to non-tabbed views
            try:
                return self.query_one(VerticalScroll)
            except NoMatches:
                return None

    def action_scroll_line_down(self) -> None:
        """Scroll the active tab's content down by one line."""
        vs = self._get_active_scroll()
        if vs is not None:
            vs.scroll_down(animate=False)

    def action_scroll_line_up(self) -> None:
        """Scroll the active tab's content up by one line."""
        vs = self._get_active_scroll()
        if vs is not None:
            vs.scroll_up(animate=False)

    def action_scroll_to_top(self) -> None:
        """Scroll the active tab's content to the top."""
        vs = self._get_active_scroll()
        if vs is not None:
            vs.scroll_home(animate=False)

    def action_scroll_to_bottom(self) -> None:
        """Scroll the active tab's content to the bottom."""
        vs = self._get_active_scroll()
        if vs is not None:
            vs.scroll_end(animate=False)

    def action_half_page_down(self) -> None:
        """Scroll the active tab's content down by half a page."""
        vs = self._get_active_scroll()
        if vs is not None:
            offset = vs.size.height // 2
            vs.scroll_relative(y=offset, animate=False)

    def action_half_page_up(self) -> None:
        """Scroll the active tab's content up by half a page."""
        vs = self._get_active_scroll()
        if vs is not None:
            offset = vs.size.height // 2
            vs.scroll_relative(y=-offset, animate=False)

    def action_open_search(self) -> None:
        """Show the search input and focus it."""
        try:
            search_input = self.query_one("#search-input", Input)
            search_input.display = True
            search_input.value = ""
            search_input.focus()
        except NoMatches:
            pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle search submission."""
        if event.input.id != "search-input":
            return

        query = event.value.strip()
        event.input.display = False
        # Defer focus to active scroll so it happens after Textual's focus cleanup
        self.call_after_refresh(self._focus_active_scroll)

        if not query:
            return

        # Get the text content from the active tab
        content = self._get_active_content_text()
        if not content:
            self._clear_search()
            return

        # Find all matches (case-insensitive), storing line numbers
        lines = content.split("\n")
        matches: list[int] = []
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        for i, line in enumerate(lines):
            if pattern.search(line):
                matches.append(i)

        if not matches:
            self.notify("No matches found")
            self._clear_search()
            return

        self.search_matches = matches
        self.search_index = 0
        self._scroll_to_match()

    def action_search_next(self) -> None:
        """Scroll to the next search match (wrapping)."""
        if not self.search_matches:
            return
        self.search_index = (self.search_index + 1) % len(self.search_matches)
        self._scroll_to_match()

    def action_search_prev(self) -> None:
        """Scroll to the previous search match (wrapping)."""
        if not self.search_matches:
            return
        self.search_index = (self.search_index - 1) % len(self.search_matches)
        self._scroll_to_match()

    def _scroll_to_match(self) -> None:
        """Scroll the active VerticalScroll to bring the current match into view."""
        if not self.search_matches:
            return
        vs = self._get_active_scroll()
        if vs is None:
            return
        line = self.search_matches[self.search_index]
        # Scroll to the approximate position — each line is roughly 1 unit
        vs.scroll_to(y=line, animate=False)

    def _get_active_content_text(self) -> str:
        """Extract plain text from the active tab's content widget."""
        try:
            tabs = self.query_one(TabbedContent)
        except NoMatches:
            # Non-tabbed view
            try:
                md = self.query_one("#detail-content", Markdown)
            except NoMatches:
                return ""
            else:
                return md.source

        active_id = tabs.active
        pane = tabs.query_one(f"#{active_id}", TabPane)
        # Try Markdown first
        try:
            md = pane.query_one(Markdown)
        except NoMatches:
            pass
        else:
            return md.source
        # Try Static — content stored as mangled __content attribute
        try:
            static = pane.query_one(Static)
        except NoMatches:
            pass
        else:
            return static.content
        return ""

    def _focus_active_scroll(self) -> None:
        """Focus the active tab's VerticalScroll widget."""
        vs = self._get_active_scroll()
        if vs is not None:
            vs.focus()

    def _clear_search(self) -> None:
        """Clear search state."""
        self.search_matches = []
        self.search_index = 0

    def action_go_back(self) -> None:
        """Return to the notification list, clearing search first if active."""
        # If search input is focused, just hide it
        try:
            search_input = self.query_one("#search-input", Input)
            if search_input.has_focus:
                search_input.display = False
                self.set_focus(None)
                self._clear_search()
                return
        except NoMatches:
            pass

        # If search is active, clear it first
        if self.search_matches:
            self._clear_search()
            return

        self.app.pop_screen()

    def action_open_palette(self) -> None:
        """Open the command palette with available review actions."""
        actions: list[tuple[str, str]] = [("refresh", "↻ Refresh")]
        if self._is_pr:
            actions = [
                ("approve", "✓ Approve"),
                ("request_changes", "✗ Request Changes"),
                *actions,
            ]

        def _on_palette_result(result: str | None) -> None:
            if result == "approve":
                self._submit_review("APPROVE")
            elif result == "request_changes":
                self._submit_review("REQUEST_CHANGES")
            elif result == "refresh":
                self.action_refresh_detail()

        self.app.push_screen(CommandPalette(actions), callback=_on_palette_result)

    def _submit_review(self, event: str) -> None:
        """Submit a PR review via the backend."""
        if self._request_queue is not None:
            self._request_queue.put_nowait(
                SubmitReviewRequest(
                    notification_id=self._notification_id,
                    event=event,
                )
            )
            self.notify(f"Review submitted: {event}")

    def _switch_tab(self, tab_id: str) -> None:
        """Activate a specific tab by pane ID."""
        try:
            tabs = self.query_one(TabbedContent)
            tabs.active = tab_id
            self._clear_search()
        except NoMatches:
            pass


def _escape(text: str) -> str:
    """Escape Rich markup characters in text."""
    return text.replace("[", r"\[")
