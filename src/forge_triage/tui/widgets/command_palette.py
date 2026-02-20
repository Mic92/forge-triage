"""Command palette — modal overlay for review actions."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.binding import BindingType


class CommandPalette(ModalScreen[str | None]):
    """A modal command palette with a filterable list of actions.

    Returns the selected action ID as a string, or None if dismissed.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss_palette", "Close", show=False),
    ]

    DEFAULT_CSS = """
    CommandPalette {
        align: center middle;
    }
    #palette-container {
        width: 60;
        max-height: 20;
        background: $surface;
        border: round $primary;
        padding: 1 2;
    }
    #palette-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #palette-input {
        margin-bottom: 1;
    }
    #palette-options {
        height: auto;
        max-height: 12;
    }
    """

    def __init__(self, actions: list[tuple[str, str]]) -> None:
        """Initialize with a list of (action_id, display_label) tuples."""
        super().__init__()
        self._actions = actions
        self._filtered_actions = list(actions)

    @property
    def action_labels(self) -> list[str]:
        """Return the display labels of all actions in order."""
        return [label for _aid, label in self._actions]

    def compose(self) -> ComposeResult:
        with Vertical(id="palette-container"):
            yield Static("Actions", id="palette-title")
            yield Input(placeholder="Type to filter…", id="palette-input")
            yield OptionList(
                *[Option(label, id=aid) for aid, label in self._actions],
                id="palette-options",
            )

    def on_mount(self) -> None:
        """Focus the filter input."""
        self.query_one("#palette-input", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter the action list as the user types."""
        query = event.value.lower()
        option_list = self.query_one("#palette-options", OptionList)
        option_list.clear_options()
        self._filtered_actions = [
            (aid, label) for aid, label in self._actions if query in label.lower()
        ]
        for aid, label in self._filtered_actions:
            option_list.add_option(Option(label, id=aid))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Return the selected action ID."""
        option_id = event.option_id
        self.dismiss(option_id)

    def on_input_submitted(self) -> None:
        """Select the first matching option on Enter."""
        if self._filtered_actions:
            self.dismiss(self._filtered_actions[0][0])
        else:
            self.dismiss(None)

    def action_dismiss_palette(self) -> None:
        """Dismiss without selecting."""
        self.dismiss(None)
