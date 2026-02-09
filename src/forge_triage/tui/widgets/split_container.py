"""Resizable split pane container with draggable divider."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.widget import Widget
from textual.widgets import Static

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.events import MouseDown, MouseMove, MouseUp


class _Divider(Static):
    """Draggable divider bar between two panes."""

    DEFAULT_CSS = """
    _Divider {
        height: 1;
        background: $primary;
        content-align: center middle;
        color: $text;
    }
    """

    def __init__(self) -> None:
        super().__init__("─" * 200)


class SplitContainer(Widget):
    """A vertical split container with a draggable divider between two children.

    The first child goes in the top pane, the second in the bottom pane.
    The divider can be dragged with the mouse to resize.
    """

    DEFAULT_CSS = """
    SplitContainer {
        height: 1fr;
        layout: vertical;
    }
    """

    MIN_PANE_HEIGHT = 3

    def __init__(
        self,
        top: Widget,
        bottom: Widget,
        *,
        initial_split: float = 0.67,
        id: str | None = None,  # noqa: A002
    ) -> None:
        super().__init__(id=id)
        self._top = top
        self._bottom = bottom
        self._split_ratio = initial_split
        self._dragging = False
        self._divider = _Divider()

    def compose(self) -> ComposeResult:
        yield self._top
        yield self._divider
        yield self._bottom

    def on_mount(self) -> None:
        """Apply initial split ratio."""
        self._apply_split()

    def on_resize(self) -> None:
        """Re-apply split on container resize."""
        self._apply_split()

    def _apply_split(self) -> None:
        """Set pane heights based on current split ratio."""
        available = self.size.height - 1  # subtract divider height
        if available < self.MIN_PANE_HEIGHT * 2:
            return
        top_height = max(self.MIN_PANE_HEIGHT, int(available * self._split_ratio))
        bottom_height = max(self.MIN_PANE_HEIGHT, available - top_height)
        # Clamp if both minimums aren't met
        if top_height + bottom_height > available:
            top_height = available - self.MIN_PANE_HEIGHT
            bottom_height = self.MIN_PANE_HEIGHT
        self._top.styles.height = top_height
        self._bottom.styles.height = bottom_height

    def on_mouse_down(self, event: MouseDown) -> None:
        """Start dragging if click is on the divider."""
        if self._is_on_divider(event.screen_y):
            self._dragging = True
            self.capture_mouse()
            event.stop()

    def on_mouse_move(self, event: MouseMove) -> None:
        """Resize panes during drag."""
        if not self._dragging:
            return
        # Calculate new split ratio from mouse position
        container_y = self.region.y
        container_height = self.size.height
        if container_height <= 1:
            return
        relative_y = event.screen_y - container_y
        new_ratio = relative_y / container_height
        # Clamp to ensure minimum pane sizes
        min_ratio = self.MIN_PANE_HEIGHT / container_height
        max_ratio = 1.0 - (self.MIN_PANE_HEIGHT / container_height)
        self._split_ratio = max(min_ratio, min(max_ratio, new_ratio))
        self._apply_split()
        event.stop()

    def on_mouse_up(self, event: MouseUp) -> None:
        """Stop dragging."""
        if self._dragging:
            self._dragging = False
            self.release_mouse()
            event.stop()

    def _is_on_divider(self, screen_y: int) -> bool:
        """Check if a screen Y coordinate is on the divider."""
        divider_region = self._divider.region
        return divider_region.y <= screen_y < divider_region.y + divider_region.height
