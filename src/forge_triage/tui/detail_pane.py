"""Detail pane widget — preview pane showing author, description, and labels."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from textual.widgets import Markdown

from forge_triage.db import get_notification, update_last_viewed
from forge_triage.pr_db import get_pr_details

if TYPE_CHECKING:
    import sqlite3


class DetailPane(Markdown):
    """Preview pane in the split layout — shows author, description, and labels."""

    def __init__(self, conn: sqlite3.Connection, *, id: str | None = None) -> None:  # noqa: A002
        super().__init__("*Select a notification to view details.*", id=id)
        self._conn = conn

    def show_notification(self, notification_id: str | None) -> None:
        """Update the pane with notification preview (author, description, labels)."""
        if notification_id is None:
            self.update("*No notification selected.*")
            return

        notif = get_notification(self._conn, notification_id)

        if notif is None:
            self.update("*Notification not found.*")
            return

        # Update last_viewed_at
        update_last_viewed(self._conn, notification_id)

        parts: list[str] = []
        parts.append(f"## {notif.subject_title}")
        parts.append(
            f"{notif.repo_owner}/{notif.repo_name}  •  {notif.subject_type}  •  {notif.reason}"
        )

        # Show PR-specific preview data if cached
        pr_details = get_pr_details(self._conn, notification_id)
        if pr_details is not None:
            parts.append(f"**Author:** {pr_details.author}")

            # Labels
            try:
                labels: list[str] = json.loads(pr_details.labels_json)
            except (json.JSONDecodeError, TypeError):
                labels = []
            if labels:
                parts.append("**Labels:** " + ", ".join(f"`{lbl}`" for lbl in labels))

            parts.append("")

            # Description — raw markdown, rendered by the Markdown widget
            if pr_details.body:
                parts.append(pr_details.body)
            else:
                parts.append("*No description provided.*")
        else:
            parts.append("")
            parts.append("*Press Enter to load full details.*")

        self.update("\n".join(parts))
