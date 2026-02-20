## ADDED Requirements

### Requirement: User-defined command configuration
The system SHALL load user-defined commands from `$XDG_CONFIG_HOME/forge-triage/commands.toml`
(defaulting to `~/.config/forge-triage/commands.toml`) at startup. Each command SHALL be
defined as a TOML array entry with a `name` string, an `args` list of strings, and a
`mode` string of either `"foreground"` or `"background"`. If the config file is absent,
the system SHALL start normally with an empty command list. If the config file is present
but malformed, the system SHALL exit before launching the TUI and print a human-readable
error message to stderr.

#### Scenario: Valid config file with commands
- **WHEN** `~/.config/forge-triage/commands.toml` contains one or more valid `[[commands]]` entries
- **THEN** the system SHALL load all commands and make them available in the action palette

#### Scenario: Missing config file
- **WHEN** no config file exists at the XDG config path
- **THEN** the system SHALL start normally with zero user-defined commands (no error)

#### Scenario: Malformed config file
- **WHEN** the config file contains invalid TOML or a command entry is missing required fields (`name`, `args`, `mode`)
- **THEN** the system SHALL print an error to stderr describing the problem and exit with a non-zero status before launching the TUI

#### Scenario: XDG_CONFIG_HOME override
- **WHEN** the `XDG_CONFIG_HOME` environment variable is set
- **THEN** the system SHALL load the config from `$XDG_CONFIG_HOME/forge-triage/commands.toml`

### Requirement: Unified action palette on PR notifications
The system SHALL open an action palette when the user presses `:` while a PR notification
is focused, in both the main notification list and the detail screen. The palette SHALL
present built-in actions first (where applicable) followed by user-defined commands. The
palette SHALL support text filtering to narrow the list. If no commands are available and
there are no built-ins to show, the system SHALL display a notification message instead of
opening an empty palette.

#### Scenario: Opening palette from main list on a PR
- **WHEN** the user presses `:` in the main notification list with a PR notification highlighted
- **THEN** the system SHALL open the command palette showing only user-defined commands (no built-in review actions)

#### Scenario: Opening palette from main list on a non-PR
- **WHEN** the user presses `:` in the main notification list with a non-PR notification highlighted (e.g. an issue)
- **THEN** the system SHALL display a notification "Not a PR" and SHALL NOT open the palette

#### Scenario: Opening palette from detail screen on a PR
- **WHEN** the user presses `:` in the detail screen for a PR notification
- **THEN** the system SHALL open the palette showing built-in actions (✓ Approve, ✗ Request Changes, ↻ Refresh) followed by all user-defined commands

#### Scenario: Opening palette from detail screen on a non-PR
- **WHEN** the user presses `:` in the detail screen for a non-PR notification
- **THEN** the system SHALL open the palette showing only ↻ Refresh (no review actions, no user commands)

#### Scenario: No user commands configured, opening from main list
- **WHEN** the user presses `:` in the main notification list with a PR highlighted AND no user-defined commands are configured
- **THEN** the system SHALL display a notification suggesting the user add commands to the config file and SHALL NOT open an empty palette

#### Scenario: Filtering the palette
- **WHEN** the palette is open and the user types text into the filter input
- **THEN** the palette SHALL show only actions whose labels contain the typed text (case-insensitive)

### Requirement: Template variable substitution in command args
The system SHALL substitute template variables in command args before execution. Supported
variables are `{pr_number}`, `{branch}`, and `{repo}`. `{repo}` SHALL always be available.
`{pr_number}` and `{branch}` SHALL only be available after PR details have been fetched.
If a command arg references a variable that is unavailable or unknown, the system SHALL
display an error notification and SHALL NOT execute the command.

#### Scenario: Substituting all variables with loaded PR details
- **WHEN** a user command with args containing `{pr_number}`, `{branch}`, and `{repo}` is selected AND PR details are loaded
- **THEN** the system SHALL substitute all three variables with the PR's number, head branch name, and `owner/repo` string respectively before executing

#### Scenario: Repo variable always available
- **WHEN** a user command using only `{repo}` is selected
- **THEN** the system SHALL substitute `{repo}` and execute the command even if PR details are not yet loaded

#### Scenario: PR details not yet loaded
- **WHEN** a user command using `{pr_number}` or `{branch}` is selected AND PR details have not yet been fetched
- **THEN** the system SHALL display a warning notification "PR details not loaded yet — try again in a moment" and SHALL NOT execute the command

#### Scenario: Branch not available
- **WHEN** a user command using `{branch}` is selected AND PR details are loaded but `head_ref` is absent
- **THEN** the system SHALL display an error notification "Branch not available for this PR" and SHALL NOT execute the command

#### Scenario: Unknown template variable
- **WHEN** a user command arg contains an unrecognised template variable (e.g. `{typo}`)
- **THEN** the system SHALL display an error notification identifying the unknown variable and SHALL NOT execute the command

### Requirement: Foreground command execution
The system SHALL execute foreground commands (`mode = "foreground"`) by suspending the TUI,
handing full terminal control to the subprocess, and restoring the TUI when the subprocess
exits. The command args SHALL be passed directly to the OS without shell interpretation.

#### Scenario: Running a foreground command
- **WHEN** the user selects a foreground command from the palette
- **THEN** the system SHALL suspend the TUI, run the command with the substituted args, and restore the TUI after the command exits

#### Scenario: Foreground execution not supported
- **WHEN** the user selects a foreground command AND the environment does not support TUI suspension (e.g. certain terminal emulators)
- **THEN** the system SHALL display an error notification "Foreground commands not supported in this environment" and SHALL NOT attempt to run the command

### Requirement: Background command execution
The system SHALL execute background commands (`mode = "background"`) by launching the
subprocess detached from the terminal's process group without capturing output. The TUI
SHALL remain active and responsive during and after the command launch.

#### Scenario: Running a background command
- **WHEN** the user selects a background command from the palette
- **THEN** the system SHALL launch the command detached from the terminal, remain fully responsive, and display no output from the command


