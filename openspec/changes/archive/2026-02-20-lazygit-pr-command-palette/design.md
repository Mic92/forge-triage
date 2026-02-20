## Context

forge-triage is a Textual TUI for GitHub PR triage. The existing `CommandPalette` widget
(`src/forge_triage/tui/widgets/command_palette.py`) is a filterable `ModalScreen` that
accepts a list of `(action_id, label)` tuples and returns a selected action ID. It is
already used in `DetailScreen.action_open_palette()` bound to `:`, showing three built-in
actions: ✓ Approve, ✗ Request Changes, ↻ Refresh.

The app currently has no configuration system — all behaviour is hardcoded. PR metadata
(number, head branch, repo name) is available via `pr_db.get_pr_details()`, but only
after the background fetch completes; at palette-open time it may not yet be present.

## Goals / Non-Goals

**Goals:**
- Let users define arbitrary named commands in `~/.config/forge-triage/commands.toml`
- Each command is an args list (no shell string) with `{pr_number}`, `{branch}`, `{repo}` template vars
- `mode = "foreground"` suspends the TUI, runs the subprocess, restores on exit
- `mode = "background"` fires and forgets (no output in TUI)
- `:` opens a unified palette merging built-in actions (Approve, Request Changes, Refresh) and user-defined commands, in both the main list and the detail screen
- Only available when the focused notification is a PR (not issues)

**Non-Goals:**
- Per-project config (XDG global only for now)
- Showing command output in the TUI (a future extension)
- Shell interpolation / piping (args list only, no shell=True)
- Editing commands from within the TUI
- A separate `a` keybinding — `:` is the single palette entry point everywhere

## Decisions

### 1. Unified palette: merge built-in actions + user commands under `:`

**Decision**: The existing `:` binding in `DetailScreen` is extended to also include
user-defined commands, appended after the built-ins. The same `:` binding is added to
`TriageApp` (main list), where it shows only user-defined commands (no built-in review
actions, since Approve/Request Changes require the full detail context).

Built-in actions always appear first; user commands follow. The existing `CommandPalette`
widget handles mixed lists natively since it just renders `(id, label)` tuples.

**Rationale**: One key, one palette — users don't need to remember `:` for built-ins vs
some other key for custom commands. Built-ins are few (3 items) and won't drown user
commands. Alphabetic filtering makes large lists navigable.

**Alternative considered**: Separate `a` key for user commands — rejected because two palette
keys for the same PR context is confusing.

---

### 2. Config loading: `tomllib` + dataclass, loaded once at startup

**Decision**: Load and parse `commands.toml` at app startup in `cli.py` / `__main__.py`,
pass the resulting `list[UserCommand]` into `TriageApp`. Validate on load; exit early with
a clear error message if the file is malformed.

**Rationale**: Loading eagerly catches config errors before the TUI starts, gives users
immediate feedback, and avoids async complexity of lazy loading. The file is small and
static for the lifetime of a session.

**Alternative considered**: Reload on each palette open — rejected because errors mid-session
are harder to surface clearly in a modal TUI.

**Config path**: XDG: `os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")` +
`/forge-triage/commands.toml`. Missing file → empty command list (no error).

---

### 3. Template substitution: `str.format_map` with a strict mapping

**Decision**: Substitute template variables using `str.format_map(vars)` where `vars` is a
`dict[str, str]` built from available PR data. Unknown keys raise `KeyError`, caught and
shown as a `notify()` error.

**Template variable sources**:
| Variable | Source | Availability |
|---|---|---|
| `{pr_number}` | `PRDetails.pr_number` | Requires PR details loaded |
| `{branch}` | `PRDetails.head_ref` | Requires PR details loaded AND `head_ref` non-None |
| `{repo}` | `notif.repo_owner + "/" + notif.repo_name` | Always available (from `Notification`) |

**`{repo}` is always available** — derived from `Notification` fields, no network fetch needed.

**If PR details not yet loaded** (`get_pr_details()` returns `None`) and the command uses
`{pr_number}` or `{branch}`: show
`notify("PR details not loaded yet — try again in a moment", severity="warning")` and abort.
This is acceptable because the detail fetch starts immediately on notification open.

**`head_ref` is `str | None`** — even when `PRDetails` is present, `head_ref` may be `None`.
`build_template_vars()` only includes `{branch}` in the dict when `head_ref` is non-`None`.
A command using `{branch}` when `head_ref is None` hits the same `KeyError` → `notify()` path
as an unknown variable, with message: `"Branch not available for this PR"`.

**Alternative considered**: Sentinel fallbacks like `"?"` — rejected because silently
running `gh pr checkout ?` is worse than a clear error.

---

### 4. Foreground execution: `app.suspend()` sync context manager

**Decision**: Use Textual's `App.suspend()` sync context manager (returns `Iterator[None]`,
not async) to hand the terminal to the subprocess:

```python
try:
    with self.app.suspend():
        subprocess.run(args, check=False)
except SuspendNotSupported:
    self.app.notify("Foreground commands not supported in this environment", severity="error")
```

`suspend()` tears down the Textual terminal driver, runs the block, then restores it.
`subprocess.run` blocks the calling thread during this window, which is acceptable because
the TUI is fully suspended. The action handler is a regular (non-async) method.

`suspend()` raises `SuspendNotSupported` if the driver doesn't support it (e.g. in tests
or certain terminal emulators) — this must be caught and shown as a `notify()` error rather
than crashing the app. `SuspendNotSupported` is importable from `textual.app`.

**Confirmed**: `App.suspend()` is available in Textual ≥ 0.39; project requires `>=0.89.0`.

**Alternative considered**: `asyncio.create_subprocess_exec` with `await` — more complex,
and `suspend()` already serialises terminal ownership cleanly.

---

### 5. Background execution: `subprocess.Popen` detached, no tracking

**Decision**: `subprocess.Popen(args, start_new_session=True)` — detaches the child from
the terminal's process group. No stdout/stderr capture. No PID tracking.

**Rationale**: Fire-and-forget is the stated requirement. `start_new_session=True` prevents
the child from receiving SIGHUP when the TUI exits.

---

### 6. Keybinding: `:` in both `TriageApp` and `DetailScreen`

**Decision**:
- `DetailScreen`: existing `:` binding calls updated `action_open_palette()` which appends
  user commands to built-in actions before pushing `CommandPalette`.
- `TriageApp`: add `Binding("colon", "open_palette", "Actions", show=True)`.
  `action_open_palette` checks that the selected notification is a PR; if not, shows
  `notify("Not a PR")`. Shows only user-defined commands (no built-in review actions).

**Confirmed**: `:` (`colon`) is free in `TriageApp`. `DetailScreen` already owns it.

---

### 7. Reuse `CommandPalette` as-is

The existing `CommandPalette(actions: list[tuple[str, str]])` modal handles mixed action
lists natively. User commands are mapped to action IDs using a `"user:<index>"` prefix to
distinguish them from built-in IDs (e.g. `"approve"`, `"refresh"`).

No changes needed to `command_palette.py`.

---

### 8. New modules and callsite changes

| Module | Responsibility |
|---|---|
| `src/forge_triage/config.py` | `UserCommand` dataclass, `load_commands(path) -> list[UserCommand]`, `get_config_path() -> Path` |
| `src/forge_triage/tui/widgets/pr_command_runner.py` | `build_template_vars(notif, pr_details) -> dict`, `run_foreground(app, args)`, `run_background(args)` |

Keeping execution logic out of `app.py` and `detail_screen.py` keeps it testable in isolation.

**Constructor chain**: `list[UserCommand]` must flow through the following callsites:
1. `cli._launch_tui()` — loads commands, passes to `TriageApp.__init__`
2. `TriageApp.__init__` — stores as `self._user_commands`, passes to `DetailScreen` when pushing it
3. `DetailScreen.__init__` — stores as `self._user_commands`, uses in `action_open_palette()`

Both `TriageApp` and `DetailScreen` constructors need a new `user_commands: list[UserCommand] = []`
parameter. The default of `[]` keeps existing test code that constructs them without the argument
working without changes.

## Risks / Trade-offs

**[Risk] PR details not loaded when `:` pressed** → Mitigated by early `notify()` + abort
for `{pr_number}` / `{branch}`. Commands using only `{repo}` always work immediately.

**[Risk] `subprocess.run` blocks the asyncio event loop during foreground commands** →
Acceptable: TUI is suspended, no events need processing.

**[Risk] `start_new_session=True` on background commands means no way to kill them if the
user quits forge-triage** → Accepted trade-off; fire-and-forget is the stated requirement.

**[Risk] Empty user command list in main list palette** → If `commands.toml` is missing or
empty and `:` is pressed from the main list (where there are no built-ins), show
`notify("No commands configured — add commands to ~/.config/forge-triage/commands.toml")`
instead of opening an empty palette.

**[Risk] `{branch}` or `{pr_number}` templating fails silently with a typo in the var name**
→ `str.format_map` raises `KeyError` on unknown keys; the handler catches it and shows
`notify(f"Unknown template variable: {e}", severity="error")`.

## Testing Strategy

**Unit tests** (`tests/test_config.py`):
- `load_commands()` with valid TOML → correct `UserCommand` list
- `load_commands()` with missing file → empty list
- `load_commands()` with malformed TOML → raises `ConfigError`
- `get_config_path()` respects `XDG_CONFIG_HOME` env var

**Unit tests** (`tests/test_pr_command_runner.py`):
- `build_template_vars()` with full PR details → correct dict with all three vars
- `build_template_vars()` with `pr_details=None` → dict contains only `{repo}`
- `build_template_vars()` with `head_ref=None` → dict omits `{branch}`

**Integration tests** (`tests/test_tui.py` extension):
- Pressing `:` on a PR in the main list → `CommandPalette` pushed with user commands
- Pressing `:` on a non-PR in the main list → `notify()` called, no palette pushed
- Pressing `:` in `DetailScreen` on a PR → palette includes both built-ins and user commands
- Empty user command list, `:` from main list → `notify()` instead of empty palette
- `SuspendNotSupported` caught and surfaced as `notify()` error

Subprocess execution paths (`run_foreground`, `run_background`) are not unit tested —
they are thin stdlib calls; the meaningful behaviour lives in template substitution and
palette guard logic, covered above.
