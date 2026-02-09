"""Detail pane widget — preview pane showing author, description, and labels."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from textual.widgets import Static

from forge_triage.db import get_notification, update_last_viewed
from forge_triage.pr_db import get_pr_details
from forge_triage.tui.widgets.markdown_light import render_markdown

if TYPE_CHECKING:
    import sqlite3


class DetailPane(Static):
    """Preview pane in the split layout — shows author, description, and labels."""

    def __init__(self, conn: sqlite3.Connection, *, id: str | None = None) -> None:  # noqa: A002
        super().__init__("Select a notification to view details.", id=id)
        self._conn = conn

    def show_notification(self, notification_id: str | None) -> None:
        """Update the pane with notification preview (author, description, labels)."""
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

        # Show PR-specific preview data if cached
        pr_details = get_pr_details(self._conn, notification_id)
        if pr_details is not None:
            parts.append(f"Author: [bold]{pr_details.author}[/bold]")

            # Labels
            try:
                labels: list[str] = json.loads(pr_details.labels_json)
            except (json.JSONDecodeError, TypeError):
                labels = []
            if labels:
                label_tags = " ".join(f"[reverse] {lbl} [/reverse]" for lbl in labels)
                parts.append(label_tags)

            parts.append("")

            # Description with light Markdown
            if pr_details.body:
                parts.append(render_markdown(pr_details.body))
            else:
                parts.append("[dim]No description provided.[/dim]")
        else:
            parts.append("")
            parts.append("[dim]Press Enter to load full details.[/dim]")

        self.update("\n".join(parts))
