"""Notification list widget — DataTable displaying prioritized notifications."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from rich.text import Text
from textual.binding import Binding
from textual.widgets import DataTable

if TYPE_CHECKING:
    import sqlite3

    from textual.binding import BindingType


def _state_icon(subject_type: str | None, subject_state: str | None) -> Text:
    """Map subject type + state to a nerdfont Octicon with color."""
    if subject_type == "Issue":
        if subject_state == "open":
            return Text("\uf41b", style="green")  # nf-oct-issue_opened
        if subject_state == "closed":
            return Text("\uf41d", style="purple")  # nf-oct-issue_closed
    elif subject_type == "PullRequest":
        if subject_state == "open":
            return Text("\uf407", style="green")  # nf-oct-git_pull_request
        if subject_state == "merged":
            return Text("\uf419", style="purple")  # nf-oct-git_merge
        if subject_state == "closed":
            return Text("\uf4dc", style="red")  # nf-oct-git_pull_request_closed
    return Text("\uf49a", style="dim")  # nf-oct-bell (unknown/null)


class NotificationList(DataTable[str | Text]):
    """A DataTable displaying notifications sorted by priority."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("j", "cursor_down", "Cursor down", show=False),
        Binding("k", "cursor_up", "Cursor up", show=False),
    ]

    def __init__(self, conn: sqlite3.Connection, *, id: str | None = None) -> None:  # noqa: A002
        super().__init__(cursor_type="row", id=id)
        self._conn = conn
        self._notification_ids: list[str] = []
        self._row_keys: list[str] = []

    def on_mount(self) -> None:
        """Set up columns and load data on mount."""
        self.add_columns("", "Repo", "Title", "Reason")
        self.refresh_data()

    def refresh_data(
        self,
        *,
        filter_text: str = "",
        filter_reason: str = "",
    ) -> None:
        """Reload notifications from DB, applying optional filters."""
        self.clear()
        self._notification_ids.clear()
        self._row_keys.clear()

        query = "SELECT * FROM notifications WHERE 1=1"
        params: list[str] = []

        if filter_text:
            query += " AND (subject_title LIKE ? OR repo_owner || '/' || repo_name LIKE ?)"
            like = f"%{filter_text}%"
            params.extend([like, like])

        if filter_reason:
            query += " AND reason = ?"
            params.append(filter_reason)

        query += " ORDER BY priority_score DESC, updated_at DESC"

        rows = self._conn.execute(query, params).fetchall()
        for row in rows:
            icon = _state_icon(row["subject_type"], row["subject_state"])
            repo = f"{row['repo_owner']}/{row['repo_name']}"
            title = row["subject_title"]
            nid = row["notification_id"]
            row_key = self.add_row(icon, repo, title, row["reason"], key=nid)
            self._notification_ids.append(nid)
            self._row_keys.append(str(row_key))

    @property
    def selected_notification_id(self) -> str | None:
        """Return the notification_id of the currently highlighted row."""
        if self.cursor_row < 0 or self.cursor_row >= len(self._notification_ids):
            return None
        return self._notification_ids[self.cursor_row]

    def remove_notification(self, notification_id: str) -> None:
        """Remove a notification from the list by ID (optimistic removal)."""
        if notification_id in self._notification_ids:
            idx = self._notification_ids.index(notification_id)
            self.remove_row(notification_id)
            self._notification_ids.pop(idx)
            self._row_keys.pop(idx)
