"""Full-screen detail view for a notification, pushed as a Textual Screen."""

from __future__ import annotations

import json
import logging
import webbrowser
from typing import TYPE_CHECKING, ClassVar

from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widgets import Footer, Header, Markdown, Static, TabbedContent, TabPane

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
        Binding("1", "tab_1", "Description", show=False),
        Binding("2", "tab_2", "Conversations", show=False),
        Binding("3", "tab_3", "Files", show=False),
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

    def compose(self) -> ComposeResult:
        notif = get_notification(self._conn, self._notification_id)
        yield Header()
        if notif is None:
            yield Static("Notification not found.")
            yield Footer()
            return

        self._is_pr = notif.subject_type == "PullRequest"

        if self._is_pr:
            with TabbedContent("Description", "Conversations", "Files Changed", id="tabs"):
                with TabPane("Description", id="tab-description"):
                    yield VerticalScroll(Markdown(id="description-content"))
                with TabPane("Conversations", id="tab-conversations"):
                    yield VerticalScroll(Markdown(id="conversations-content"))
                with TabPane("Files Changed", id="tab-files"):
                    yield VerticalScroll(Static(id="files-content"))
        else:
            with VerticalScroll():
                yield Markdown(id="detail-content")

        yield Footer()

    def on_mount(self) -> None:
        """Load initial content."""
        self._render_content()

    def _render_content(self) -> None:
        """Render content into the appropriate widgets."""
        notif = get_notification(self._conn, self._notification_id)
        if notif is None:
            return

        if self._is_pr:
            self._render_description_tab(notif)
            self._render_conversations_tab()
            self._render_files_tab()
        else:
            self._render_issue_view(notif)

    def _render_description_tab(self, notif: Notification) -> None:
        """Render the Description tab with PR metadata and body as Markdown."""
        parts: list[str] = []
        parts.append(f"# {notif.subject_title}")
        parts.append(
            f"{notif.repo_owner}/{notif.repo_name}  •  {notif.subject_type}  •  {notif.reason}"
        )

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
            parts.append("*PR details not loaded. Press `r` to refresh.*")

        self._update_markdown("#description-content", "\n".join(parts))

    def _render_conversations_tab(self) -> None:
        """Render the Conversations tab with review threads."""
        threads = get_review_threads(self._conn, self._notification_id)

        if not threads:
            self._update_markdown("#conversations-content", "*No conversations yet.*")
            return

        parts: list[str] = []
        # Group by thread_id
        thread_groups: dict[str | None, list[ReviewComment]] = {}
        for comment in threads:
            thread_groups.setdefault(comment.thread_id, []).append(comment)

        for comments in thread_groups.values():
            first = comments[0]
            resolved = " (Resolved)" if first.is_resolved else ""
            location = f"{first.path}:{first.line}" if first.line is not None else first.path
            parts.append(f"### `{location}`{resolved}")
            parts.append("")

            for c in comments:
                parts.append(f"**{c.author}** — {c.created_at}")
                parts.append("")
                parts.append(c.body)
                parts.append("")

            parts.append("---")
            parts.append("")

        self._update_markdown("#conversations-content", "\n".join(parts))

    def _render_files_tab(self) -> None:
        """Render the Files Changed tab with diff summaries."""
        files = get_pr_files(self._conn, self._notification_id)

        if not files:
            self._update_static(
                "#files-content",
                "[dim]No files changed data loaded. Press [bold]r[/bold] to refresh.[/dim]",
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
        parts.append(
            f"{notif.repo_owner}/{notif.repo_name}  •  {notif.subject_type}  •  {notif.reason}"
        )
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

    def action_go_back(self) -> None:
        """Return to the notification list."""
        self.app.pop_screen()

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
                MarkDoneRequest(notification_ids=[self._notification_id])
            )
        self.app.pop_screen()

    def action_show_help(self) -> None:
        """Show help screen."""
        self.app.push_screen(HelpScreen(context="detail"))

    def action_tab_1(self) -> None:
        """Switch to Description tab."""
        self._switch_tab("tab-description")

    def action_tab_2(self) -> None:
        """Switch to Conversations tab."""
        self._switch_tab("tab-conversations")

    def action_tab_3(self) -> None:
        """Switch to Files Changed tab."""
        self._switch_tab("tab-files")

    def action_open_palette(self) -> None:
        """Open the command palette with available review actions."""
        actions: list[tuple[str, str]] = [
            ("approve", "✓ Approve"),
            ("request_changes", "✗ Request Changes"),
            ("refresh", "↻ Refresh"),
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
        except NoMatches:
            pass


def _escape(text: str) -> str:
    """Escape Rich markup characters in text."""
    return text.replace("[", r"\[")
