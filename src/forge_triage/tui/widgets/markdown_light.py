"""Light Markdown-to-Rich-markup converter.

Handles: headings, bold, italic, inline code, fenced code blocks.
Does NOT handle: tables, images, checkboxes, nested lists.
"""

from __future__ import annotations

import re


def render_markdown(text: str) -> str:
    """Convert a Markdown string to Rich console markup."""
    if not text:
        return ""

    lines = text.split("\n")
    output: list[str] = []
    in_code_block = False
    code_lines: list[str] = []

    for line in lines:
        # Fenced code block toggle
        if line.startswith("```"):
            if in_code_block:
                # End code block — emit as dim indented block
                output.append("[dim]" + "\n".join(f"  {cl}" for cl in code_lines) + "[/dim]")
                code_lines = []
                in_code_block = False
            else:
                in_code_block = True
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        # Headings
        heading_match = re.match(r"^(#{1,6})\s+(.*)", line)
        if heading_match:
            output.append(f"[bold]{heading_match.group(2)}[/bold]")
            continue

        # Inline formatting
        converted = _convert_inline(line)
        output.append(converted)

    # Unclosed code block — flush remaining
    if code_lines:
        output.append("[dim]" + "\n".join(f"  {cl}" for cl in code_lines) + "[/dim]")

    return "\n".join(output)


def _convert_inline(line: str) -> str:
    """Apply inline Markdown formatting to a single line."""
    # Bold: **text** or __text__
    line = re.sub(r"\*\*(.+?)\*\*", r"[bold]\1[/bold]", line)
    line = re.sub(r"__(.+?)__", r"[bold]\1[/bold]", line)
    # Italic: *text* or _text_ (but not inside bold markers)
    line = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"[italic]\1[/italic]", line)
    line = re.sub(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", r"[italic]\1[/italic]", line)
    # Inline code: `code`
    return re.sub(r"`([^`]+)`", r"[bold cyan]\1[/bold cyan]", line)
