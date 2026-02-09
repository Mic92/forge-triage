"""Detail pane widget — shows notification metadata and comments."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.widgets import Static

from forge_triage.db import get_comments, get_notification, update_last_viewed

if TYPE_CHECKING:
    import sqlite3


class DetailPane(Static):
    """Displays the full detail of the selected notification."""

    def __init__(self, conn: sqlite3.Connection, *, id: str | None = None) -> None:  # noqa: A002
        super().__init__("Select a notification to view details.", id=id)
        self._conn = conn

    def show_notification(self, notification_id: str | None) -> None:
        """Update the pane with notification details and comments."""
        if notification_id is None:
            self.update("No notification selected.")
            return

        notif = get_notification(self._conn, notification_id)

        if notif is None:
            self.update("Notification not found.")
            return

        # Update last_viewed_at
        update_last_viewed(self._conn, notification_id)

        parts: list[str] = []
        parts.append(f"[bold]{notif.subject_title}[/bold]")
        parts.append(
            f"{notif.repo_owner}/{notif.repo_name}  •  {notif.subject_type}  •  {notif.reason}"
        )
        if notif.ci_status:
            ci_style = "green" if notif.ci_status == "success" else "red"
            parts.append(f"CI: [{ci_style}]{notif.ci_status}[/{ci_style}]")
        parts.append("")

        # Comments
        comments = get_comments(self._conn, notification_id)
        last_viewed = notif.last_viewed_at

        if notif.comments_loaded and comments:
            parts.append(f"[bold]Comments ({len(comments)}):[/bold]")
            parts.append("")
            for comment in comments:
                is_new = last_viewed is not None and comment.created_at > last_viewed
                author_style = "[bold yellow]" if is_new else "[bold]"
                parts.append(f"{author_style}{comment.author}[/] — {comment.created_at}")
                parts.append(comment.body)
                parts.append("")
        elif not notif.comments_loaded:
            parts.append("[dim]Loading comments…[/dim]")
        else:
            parts.append("[dim]No comments.[/dim]")

        self.update("\n".join(parts))
