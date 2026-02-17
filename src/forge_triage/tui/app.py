"""Textual App — main TUI entry point."""

from __future__ import annotations

import asyncio
import webbrowser
from typing import TYPE_CHECKING, ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.widgets import Footer, Header, Input, Static

from forge_triage.db import get_notification, get_notification_count, open_db
from forge_triage.messages import (
    ErrorResult,
    FetchCommentsRequest,
    FetchCommentsResult,
    FetchPRDetailResult,
    MarkDoneRequest,
    MarkDoneResult,
    PostReviewCommentResult,
    PreLoadComplete,
    Request,
    ResolveThreadResult,
    Response,
    SubmitReviewResult,
)
from forge_triage.tui.detail_pane import DetailPane
from forge_triage.tui.detail_screen import DetailScreen
from forge_triage.tui.help_screen import HelpScreen
from forge_triage.tui.notification_list import NotificationList
from forge_triage.tui.widgets.split_container import SplitContainer

if TYPE_CHECKING:
    import sqlite3

    from textual.binding import BindingType

POLL_INTERVAL = 0.1


class TriageApp(App[None]):
    """GitHub notification triage TUI."""

    TITLE = "forge-triage"

    CSS = """
    #main-container {
        height: 1fr;
    }
    #list-pane {
        overflow-y: auto;
    }
    #detail-pane {
        padding: 1 2;
        overflow-y: auto;
    }
    #filter-input {
        dock: bottom;
        display: none;
    }
    #empty-message {
        width: 100%;
        height: 100%;
        content-align: center middle;
        text-style: dim;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "quit", "Quit", show=True),
        Binding("question_mark", "show_help", "Help", show=True),
        Binding("d", "mark_done", "Done", show=True, priority=True),
        Binding("o", "open_browser", "Open", show=True),
        Binding("slash", "start_filter", "Filter", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("escape", "clear_filter", "Clear", show=True),
    ]

    def __init__(
        self,
        conn: sqlite3.Connection | None = None,
        request_queue: asyncio.Queue[Request] | None = None,
        response_queue: asyncio.Queue[Response] | None = None,
    ) -> None:
        super().__init__()
        self._conn = conn if conn is not None else open_db()
        self._owns_conn = conn is None
        self._request_queue: asyncio.Queue[Request] = (
            request_queue if request_queue is not None else asyncio.Queue()
        )
        self._response_queue: asyncio.Queue[Response] = (
            response_queue if response_queue is not None else asyncio.Queue()
        )
        self._filter_text = ""

    def compose(self) -> ComposeResult:
        """Create the split-pane layout."""
        yield Header()
        total = get_notification_count(self._conn)
        if total == 0:
            with Vertical(id="main-container"):
                yield Static(
                    "Inbox is empty. Run [bold]forge-triage sync[/bold] to fetch notifications.",
                    id="empty-message",
                )
        else:
            yield SplitContainer(
                NotificationList(self._conn, id="list-pane"),
                DetailPane(self._conn, id="detail-pane"),
                id="main-container",
            )
        yield Input(placeholder="Filter…", id="filter-input")
        yield Footer()

    def on_mount(self) -> None:
        """Start polling the response queue."""
        self.set_interval(POLL_INTERVAL, self._poll_responses)
        # Focus the notification list
        nlist = self._get_notification_list()
        if nlist is not None:
            self.set_focus(nlist)
            if nlist.selected_notification_id:
                detail = self._get_detail_pane()
                if detail is not None:
                    detail.show_notification(nlist.selected_notification_id)
                    self._maybe_fetch_comments(nlist.selected_notification_id)

    def _get_notification_list(self) -> NotificationList | None:
        try:
            return self.query_one(NotificationList)
        except NoMatches:
            return None

    def _get_detail_pane(self) -> DetailPane | None:
        try:
            return self.query_one(DetailPane)
        except NoMatches:
            return None

    def on_data_table_row_selected(self) -> None:
        """Open the detail view when Enter is pressed on a row."""
        self.action_open_detail()

    def on_data_table_row_highlighted(self) -> None:
        """Update detail pane when cursor moves."""
        nlist = self._get_notification_list()
        detail = self._get_detail_pane()
        if nlist is not None and detail is not None:
            nid = nlist.selected_notification_id
            detail.show_notification(nid)
            if nid is not None:
                self._maybe_fetch_comments(nid)

    def _maybe_fetch_comments(self, notification_id: str) -> None:
        """Post FetchCommentsRequest if comments aren't loaded."""
        notif = get_notification(self._conn, notification_id)
        if notif is not None and not notif.comments_loaded:
            self._request_queue.put_nowait(FetchCommentsRequest(notification_id=notification_id))

    async def _poll_responses(self) -> None:
        """Drain the response queue and update the UI."""
        while not self._response_queue.empty():
            try:
                resp = self._response_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            self._handle_response(resp)

    def _handle_response(self, resp: Response) -> None:
        """Dispatch a response message to the appropriate handler."""
        if isinstance(resp, MarkDoneResult):
            self._on_mark_done_result(resp)
        elif isinstance(resp, FetchCommentsResult):
            self._on_fetch_comments_result(resp)
        elif isinstance(resp, PreLoadComplete):
            self._on_preload_complete(resp)
        elif isinstance(resp, FetchPRDetailResult):
            self._on_fetch_pr_detail_result(resp)
        elif isinstance(resp, PostReviewCommentResult):
            self._on_post_review_comment_result(resp)
        elif isinstance(resp, SubmitReviewResult):
            self._on_submit_review_result(resp)
        elif isinstance(resp, ResolveThreadResult):
            self._on_resolve_thread_result(resp)
        elif isinstance(resp, ErrorResult):
            self._on_error_result(resp)

    def _on_mark_done_result(self, result: MarkDoneResult) -> None:
        """Handle mark-done result — confirm or rollback."""
        if result.errors:
            nlist = self._get_notification_list()
            if nlist is not None:
                nlist.refresh_data(filter_text=self._filter_text)
            self.notify(f"Error: {', '.join(result.errors)}", severity="error")

    def _on_fetch_comments_result(self, result: FetchCommentsResult) -> None:
        """Handle fetched comments — refresh detail if viewing this notification."""
        nlist = self._get_notification_list()
        detail = self._get_detail_pane()
        if (
            nlist is not None
            and detail is not None
            and nlist.selected_notification_id == result.notification_id
        ):
            detail.show_notification(result.notification_id)

    def _on_preload_complete(self, _result: PreLoadComplete) -> None:
        """Handle preload complete — refresh detail if needed."""
        nlist = self._get_notification_list()
        detail = self._get_detail_pane()
        if nlist is not None and detail is not None:
            nid = nlist.selected_notification_id
            if nid is not None:
                detail.show_notification(nid)

    def _on_fetch_pr_detail_result(self, result: FetchPRDetailResult) -> None:
        """Handle fetched PR details — refresh detail screen if active."""
        if result.success:
            # If we're on the detail screen, re-render
            if isinstance(self.screen, DetailScreen):
                self.screen.refresh_content()
            self.notify("PR details loaded")
        else:
            self.notify(f"Failed to load PR details: {result.error}", severity="error")

    def _on_post_review_comment_result(self, result: PostReviewCommentResult) -> None:
        """Handle review comment result — confirm or show error."""
        if result.success:
            self.notify("Comment posted")
        else:
            self.notify(f"Comment failed: {result.error}", severity="error")

    def _on_submit_review_result(self, result: SubmitReviewResult) -> None:
        """Handle review submission result — confirm or show error."""
        if result.success:
            self.notify("Review submitted")
        else:
            self.notify(f"Review failed: {result.error}", severity="error")

    def _on_resolve_thread_result(self, result: ResolveThreadResult) -> None:
        """Handle thread resolve result — confirm or show error."""
        if result.success:
            self.notify("Thread updated")
        else:
            self.notify(f"Thread update failed: {result.error}", severity="error")

    def _on_error_result(self, result: ErrorResult) -> None:
        """Handle error — show notification."""
        self.notify(f"Error ({result.request_type}): {result.error}", severity="error")

    # === Actions ===

    def action_mark_done(self) -> None:
        """Mark the highlighted notification as done (optimistic)."""
        nlist = self._get_notification_list()
        if nlist is None:
            return
        nid = nlist.selected_notification_id
        if nid is None:
            return
        nlist.remove_notification(nid)
        self._request_queue.put_nowait(MarkDoneRequest(notification_ids=(nid,)))

    def action_open_browser(self) -> None:
        """Open the highlighted notification's URL in the browser."""
        nlist = self._get_notification_list()
        if nlist is None:
            return
        nid = nlist.selected_notification_id
        if nid is None:
            return
        notif = get_notification(self._conn, nid)
        if notif is not None and notif.html_url:
            webbrowser.open(notif.html_url)

    def action_start_filter(self) -> None:
        """Show the filter input."""
        filter_input = self.query_one("#filter-input", Input)
        filter_input.styles.display = "block"
        filter_input.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Apply the text filter."""
        if event.input.id != "filter-input":
            return
        self._filter_text = event.value
        filter_input = self.query_one("#filter-input", Input)
        filter_input.styles.display = "none"
        nlist = self._get_notification_list()
        if nlist is not None:
            nlist.refresh_data(filter_text=self._filter_text)
            self.set_focus(nlist)

    def action_refresh(self) -> None:
        """Reload notification list from the database."""
        nlist = self._get_notification_list()
        if nlist is not None:
            nlist.refresh_data(filter_text=self._filter_text)
            self.set_focus(nlist)
        self.notify("Refreshed")

    def action_clear_filter(self) -> None:
        """Clear all filters."""
        if not self._filter_text:
            return
        self._filter_text = ""
        filter_input = self.query_one("#filter-input", Input)
        filter_input.styles.display = "none"
        filter_input.value = ""
        nlist = self._get_notification_list()
        if nlist is not None:
            nlist.refresh_data()
            self.set_focus(nlist)

    def action_open_detail(self) -> None:
        """Open the full-screen detail view for the selected notification."""
        nlist = self._get_notification_list()
        if nlist is None:
            return
        nid = nlist.selected_notification_id
        if nid is None:
            return
        self.push_screen(DetailScreen(self._conn, nid, request_queue=self._request_queue))

    def action_show_help(self) -> None:
        """Show the help overlay."""
        self.push_screen(HelpScreen())

    def on_unmount(self) -> None:
        """Clean up."""
        if self._owns_conn:
            self._conn.close()
