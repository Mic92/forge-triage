"""Inline reply editor widget for review conversations."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget
from textual.widgets import TextArea

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.binding import BindingType


class ReplyEditor(Widget):
    """An inline TextArea for composing replies to review threads.

    Posts a ReplySubmitted message on Ctrl+Enter, ReplyCancelled on Escape.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+s", "submit_reply", "Submit", show=True),
        Binding("escape", "cancel_reply", "Cancel", show=True),
    ]

    DEFAULT_CSS = """
    ReplyEditor {
        height: auto;
        max-height: 10;
        border: round $accent;
        padding: 0 1;
    }
    ReplyEditor TextArea {
        height: auto;
        min-height: 3;
        max-height: 8;
    }
    """

    class ReplySubmitted(Message):
        """Posted when the user submits a reply."""

        def __init__(self, body: str, thread_id: str) -> None:
            super().__init__()
            self.body = body
            self.thread_id = thread_id

    class ReplyCancelled(Message):
        """Posted when the user cancels the reply."""

    def __init__(self, thread_id: str, *, id: str | None = None) -> None:  # noqa: A002
        super().__init__(id=id)
        self.reply_thread_id = thread_id

    def compose(self) -> ComposeResult:
        yield TextArea(id="reply-text")

    def on_mount(self) -> None:
        """Focus the text area."""
        self.query_one(TextArea).focus()

    def action_submit_reply(self) -> None:
        """Submit the reply if non-empty."""
        text_area = self.query_one(TextArea)
        body = text_area.text.strip()
        if body:
            self.post_message(self.ReplySubmitted(body=body, thread_id=self.reply_thread_id))
        else:
            self.notify("Cannot submit an empty reply.")

    def action_cancel_reply(self) -> None:
        """Cancel the reply."""
        self.post_message(self.ReplyCancelled())
