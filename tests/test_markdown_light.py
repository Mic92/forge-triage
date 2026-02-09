"""Tests for the light Markdown-to-Rich-markup converter."""

from __future__ import annotations

from forge_triage.tui.widgets.markdown_light import render_markdown


def test_fenced_code_block_preserves_surrounding_text() -> None:
    """Fenced code block with language hint renders without eating before/after text."""
    md = "Before\n```python\ndef foo():\n    pass\n```\nAfter"
    result = render_markdown(md)
    assert "def foo():" in result
    assert "Before" in result
    assert "After" in result
