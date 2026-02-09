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
    MarkDoneRequest,
    MarkDoneResult,
    PreLoadCommentsRequest,
    PreLoadComplete,
)
from forge_triage.tui.detail_pane import DetailPane
from forge_triage.tui.help_screen import HelpScreen
from forge_triage.tui.notification_list import NotificationList

if TYPE_CHECKING:
    import sqlite3

    from textual.binding import BindingType

type _Request = MarkDoneRequest | FetchCommentsRequest | PreLoadCommentsRequest
type _Response = MarkDoneResult | FetchCommentsResult | PreLoadComplete | ErrorResult

POLL_INTERVAL = 0.1


class TriageApp(App[None]):
    """GitHub notification triage TUI."""

    TITLE = "forge-triage"

    CSS = """
    #main-container {
        height: 1fr;
    }
    #list-pane {
        height: 2fr;
        border-bottom: solid $primary;
    }
    #detail-pane {
        height: 1fr;
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
        Binding("D", "bulk_done", "Bulk Done", show=True, key_display="D"),
        Binding("o", "open_browser", "Open", show=True),
        Binding("slash", "start_filter", "Filter", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("escape", "clear_filter", "Clear", show=True),
        Binding("x", "toggle_select", "Select"),
        Binding("asterisk", "select_all", "Select All"),
        Binding("g", "toggle_group", "Group"),
    ]

    def __init__(
        self,
        conn: sqlite3.Connection | None = None,
        request_queue: asyncio.Queue[_Request] | None = None,
        response_queue: asyncio.Queue[_Response] | None = None,
    ) -> None:
        super().__init__()
        self._conn = conn if conn is not None else open_db()
        self._owns_conn = conn is None
        self._request_queue: asyncio.Queue[_Request] = (
            request_queue if request_queue is not None else asyncio.Queue()
        )
        self._response_queue: asyncio.Queue[_Response] = (
            response_queue if response_queue is not None else asyncio.Queue()
        )
        self._selected: set[str] = set()
        self._filter_text = ""

    def compose(self) -> ComposeResult:
        """Create the split-pane layout."""
        yield Header()
        with Vertical(id="main-container"):
            total = get_notification_count(self._conn)
            if total == 0:
                yield Static(
                    "Inbox is empty. Run [bold]forge-triage sync[/bold] to fetch notifications.",
                    id="empty-message",
                )
            else:
                yield NotificationList(self._conn, id="list-pane")
                yield DetailPane(self._conn, id="detail-pane")
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

    def _handle_response(self, resp: _Response) -> None:
        """Dispatch a response message to the appropriate handler."""
        if isinstance(resp, MarkDoneResult):
            self._on_mark_done_result(resp)
        elif isinstance(resp, FetchCommentsResult):
            self._on_fetch_comments_result(resp)
        elif isinstance(resp, PreLoadComplete):
            self._on_preload_complete(resp)
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
        self._request_queue.put_nowait(MarkDoneRequest(notification_ids=[nid]))

    def action_bulk_done(self) -> None:
        """Mark all selected notifications as done."""
        if not self._selected:
            return
        nlist = self._get_notification_list()
        if nlist is None:
            return
        ids = list(self._selected)
        for nid in ids:
            nlist.remove_notification(nid)
        self._selected.clear()
        self._request_queue.put_nowait(MarkDoneRequest(notification_ids=ids))

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
        self._filter_text = ""
        filter_input = self.query_one("#filter-input", Input)
        filter_input.styles.display = "none"
        filter_input.value = ""
        nlist = self._get_notification_list()
        if nlist is not None:
            nlist.refresh_data()
            self.set_focus(nlist)

    def action_toggle_select(self) -> None:
        """Toggle selection on the current notification."""
        nlist = self._get_notification_list()
        if nlist is None:
            return
        nid = nlist.selected_notification_id
        if nid is None:
            return
        if nid in self._selected:
            self._selected.discard(nid)
        else:
            self._selected.add(nid)

    def action_select_all(self) -> None:
        """Select all visible notifications."""
        nlist = self._get_notification_list()
        if nlist is None:
            return
        self._selected = set(nlist._notification_ids)  # noqa: SLF001

    def action_toggle_group(self) -> None:
        """Toggle grouped-by-repo view (placeholder)."""
        self.notify("Grouping not yet implemented")

    def action_show_help(self) -> None:
        """Show the help overlay."""
        self.push_screen(HelpScreen())

    def on_unmount(self) -> None:
        """Clean up."""
        if self._owns_conn:
            self._conn.close()
