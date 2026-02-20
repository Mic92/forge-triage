## Why

Power users need to run arbitrary external commands against a selected PR (e.g. `gh pr checkout`, custom scripts, CI triggers) without leaving the TUI. Hard-coding these actions is impractical — users have different workflows — so the palette must be user-configurable.

## What Changes

- Add a `~/.config/forge-triage/commands.toml` config file that lets users define a list of named commands with arg templates and an execution mode (`foreground` / `background`)
- Add a command palette modal (reusing the existing `CommandPalette` widget) that opens when the user presses `a`, populates itself from the config, substitutes PR template variables into args, then executes the selected command
- Bind `a` in both the main notification list and the detail screen, but only when the focused item is a PR notification (not issues or other types)
- Foreground commands suspend the TUI, hand the terminal to the subprocess, then restore the TUI when the subprocess exits
- Background commands are fire-and-forget (no output shown in the TUI)

## Capabilities

### New Capabilities
- `pr-user-commands`: User-defined command palette for PR notifications — config file format, template variable substitution (`{pr_number}`, `{branch}`, `{repo}`), foreground/background execution, and `a` keybinding in main list and detail screen

### Modified Capabilities
- `tui-triage`: New `a` keybinding added to the main notification list (PR context only)

## Impact

- **New file**: `src/forge_triage/config.py` — loads and validates `commands.toml`
- **New file**: `src/forge_triage/tui/widgets/pr_command_runner.py` — template substitution + subprocess execution (fg/bg)
- **Modified**: `src/forge_triage/tui/app.py` — bind `a`, push `CommandPalette` with user commands, dispatch execution
- **Modified**: `src/forge_triage/tui/detail_screen.py` — same `a` binding in detail view
- **Existing**: `src/forge_triage/tui/widgets/command_palette.py` — reused as-is, no changes needed
- **Dependencies**: stdlib `subprocess`, `tomllib` (Python 3.11+ built-in) — no new third-party deps
- **Config path**: `$XDG_CONFIG_HOME/forge-triage/commands.toml` (defaults to `~/.config/forge-triage/commands.toml`)
