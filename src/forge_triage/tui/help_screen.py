"""Help screen — modal overlay showing keybindings."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.containers import Center, Middle
from textual.screen import ModalScreen
from textual.widgets import Static

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.binding import BindingType

_HELP_TEXT = """\
[bold]Keybindings[/bold]

  [bold]j / ↓[/bold]     Move down
  [bold]k / ↑[/bold]     Move up
  [bold]d[/bold]         Mark done (single)
  [bold]D[/bold]         Mark done (selected)
  [bold]x[/bold]         Toggle selection
  [bold]*[/bold]         Select all visible
  [bold]o[/bold]         Open in browser
  [bold]/[/bold]         Filter by text
  [bold]r[/bold]         Filter by reason
  [bold]Escape[/bold]    Clear filter
  [bold]g[/bold]         Toggle repo grouping
  [bold]?[/bold]         This help
  [bold]q[/bold]         Quit

Press [bold]?[/bold] or [bold]Escape[/bold] to dismiss.
"""


class HelpScreen(ModalScreen[None]):
    """Modal help overlay showing all keybindings."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "dismiss_help", "Close"),
        ("question_mark", "dismiss_help", "Close"),
    ]

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    HelpScreen > Center > Middle > Static {
        width: 50;
        padding: 2 4;
        background: $surface;
        border: tall $primary;
    }
    """

    def compose(self) -> ComposeResult:
        """Create the help content."""
        with Center(), Middle():
            yield Static(_HELP_TEXT, markup=True)

    def action_dismiss_help(self) -> None:
        """Dismiss the help screen."""
        self.dismiss(None)
