## 1. Config module (`src/forge_triage/config.py`)

- [x] 1.1 Write failing tests for `get_config_path()`: respects `XDG_CONFIG_HOME` env var, falls back to `~/.config/forge-triage/commands.toml`
- [x] 1.2 Implement `get_config_path() -> Path`
- [x] 1.3 Write failing tests for `load_commands()`: valid TOML returns correct `list[UserCommand]`, missing file returns `[]`, malformed TOML raises `ConfigError`, missing required field raises `ConfigError`
- [x] 1.4 Implement `UserCommand` dataclass and `ConfigError`, `load_commands(path: Path) -> list[UserCommand]`
- [x] 1.5 `ruff format`, `ruff check`, `mypy` on `config.py` and `test_config.py`

## 2. Template variable builder (`src/forge_triage/tui/widgets/pr_command_runner.py`)

- [x] 2.1 Write failing tests for `build_template_vars()`: full PR details → dict with all three vars; `pr_details=None` → dict with only `{repo}`; `head_ref=None` → dict omits `{branch}`
- [x] 2.2 Implement `build_template_vars(notif: Notification, pr_details: PRDetails | None) -> dict[str, str]`
- [x] 2.3 Implement `run_foreground(app: App, args: list[str]) -> None` — `try: with app.suspend(): subprocess.run(args)` catching `SuspendNotSupported`
- [x] 2.4 Implement `run_background(args: list[str]) -> None` — `subprocess.Popen(args, start_new_session=True)`
- [x] 2.5 `ruff format`, `ruff check`, `mypy` on `pr_command_runner.py` and `test_pr_command_runner.py`

## 3. Thread `user_commands` through the constructor chain

- [x] 3.1 Add `user_commands: list[UserCommand] = []` param to `TriageApp.__init__`, store as `self._user_commands`
- [x] 3.2 Add `user_commands: list[UserCommand] = []` param to `DetailScreen.__init__`, store as `self._user_commands`
- [x] 3.3 Update `TriageApp.action_open_detail()` to pass `self._user_commands` when pushing `DetailScreen`
- [x] 3.4 Update `cli._launch_tui()` to call `load_commands(get_config_path())`, print error and exit on `ConfigError`, pass result to `TriageApp`
- [x] 3.5 `ruff format`, `ruff check`, `mypy` on changed files; confirm existing tests still pass

## 4. Unified palette in `DetailScreen`

- [x] 4.1 Write failing test: pressing `:` in `DetailScreen` on a PR → palette action list includes built-ins (approve, request_changes, refresh) followed by user commands
- [x] 4.2 Update `DetailScreen.action_open_palette()` to append `("user:<i>", cmd.name)` entries for each `UserCommand` in `self._user_commands` after built-ins
- [x] 4.3 Update `_on_palette_result` callback to handle `"user:<i>"` IDs: call `build_template_vars()`, show `notify()` on missing vars, dispatch `run_foreground()` or `run_background()`
- [x] 4.4 Write failing test: `SuspendNotSupported` during foreground execution → `notify()` error shown, app does not crash
- [x] 4.5 Verify the `SuspendNotSupported` path via the test (implementation already handles it from 2.3)
- [x] 4.6 `ruff format`, `ruff check`, `mypy`

## 5. Palette in `TriageApp` main list

- [x] 5.1 Write failing test: pressing `:` on a PR notification in the main list → `CommandPalette` pushed with user commands
- [x] 5.2 Write failing test: pressing `:` on a non-PR notification → `notify("Not a PR")`, no palette pushed
- [x] 5.3 Write failing test: pressing `:` on a PR with no user commands configured → `notify(...)` suggesting config file, no palette pushed
- [x] 5.4 Add `Binding("colon", "open_palette", "Actions", show=True)` to `TriageApp.BINDINGS`
- [x] 5.5 Implement `TriageApp.action_open_palette()`: guard on PR type, guard on empty command list, push `CommandPalette`, dispatch execution in callback
- [x] 5.6 `ruff format`, `ruff check`, `mypy`

## 6. Final verification

- [x] 6.1 Run full test suite (`pytest`) — all tests pass
- [x] 6.2 `ruff format --check`, `ruff check`, `mypy` across entire `src/` and `tests/`
- [ ] 6.3 Manual smoke test: add a command to `~/.config/forge-triage/commands.toml`, launch TUI, press `:` on a PR, verify command appears and executes
