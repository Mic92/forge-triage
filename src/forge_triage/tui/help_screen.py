"""Help screen — modal overlay showing keybindings."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.containers import Center, Middle
from textual.screen import ModalScreen
from textual.widgets import Static

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.binding import BindingType

_LIST_HELP = """\
[bold]Notification List Keybindings[/bold]

  [bold]j / ↓[/bold]     Move down
  [bold]k / ↑[/bold]     Move up
  [bold]Enter[/bold]     Open detail view
  [bold]d[/bold]         Mark done (single)
  [bold]D[/bold]         Mark done (selected)
  [bold]x[/bold]         Toggle selection
  [bold]*[/bold]         Select all visible
  [bold]o[/bold]         Open in browser
  [bold]/[/bold]         Filter by text
  [bold]r[/bold]         Refresh list
  [bold]Escape[/bold]    Clear filter
  [bold]?[/bold]         This help
  [bold]q[/bold]         Quit

Press [bold]?[/bold] or [bold]Escape[/bold] to dismiss.
"""

_DETAIL_HELP = """\
[bold]Detail View Keybindings[/bold]

[bold]Tabs[/bold]
  [bold]1[/bold] / [bold]2[/bold]       Conversation / Files Changed
  [bold]Tab[/bold]       Next tab
  [bold]Shift+Tab[/bold] Previous tab
  [bold]h[/bold] / [bold]l[/bold]       Previous / Next tab

[bold]Scrolling[/bold]
  [bold]j[/bold] / [bold]k[/bold]       Scroll down / up
  [bold]g[/bold] / [bold]G[/bold]       Jump to top / bottom
  [bold]Home[/bold] / [bold]End[/bold]  Jump to top / bottom
  [bold]Ctrl+d[/bold]    Half page down
  [bold]Ctrl+u[/bold]    Half page up

[bold]Search[/bold]
  [bold]/[/bold]         Search in tab
  [bold]n[/bold] / [bold]N[/bold]       Next / Previous match
  [bold]Escape[/bold]    Clear search

[bold]Actions[/bold]
  [bold]d[/bold]         Mark done & go back
  [bold]o[/bold]         Open in browser
  [bold]r[/bold]         Refresh PR data
  [bold]:[/bold]         Open command palette
  [bold]Ctrl+p[/bold]   Open command palette
  [bold]Escape[/bold]    Go back
  [bold]?[/bold]         This help
  [bold]q[/bold]         Go back

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

    def __init__(self, *, context: str = "list") -> None:
        """Initialize with context: 'list' for main view, 'detail' for detail view."""
        super().__init__()
        self._help_context = context

    def compose(self) -> ComposeResult:
        """Create the help content."""
        text = _DETAIL_HELP if self._help_context == "detail" else _LIST_HELP
        with Center(), Middle():
            yield Static(text, markup=True)

    def action_dismiss_help(self) -> None:
        """Dismiss the help screen."""
        self.dismiss(None)
