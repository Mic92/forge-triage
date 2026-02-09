## ADDED Requirements

### Requirement: List notifications from CLI
The system SHALL provide a CLI subcommand to list notifications in a human-readable format.

#### Scenario: List all notifications
- **WHEN** the user runs `forge-triage ls`
- **THEN** the system SHALL print all notifications sorted by priority, showing: priority tier indicator, repo name, subject number, title, and reason

#### Scenario: List with JSON output
- **WHEN** the user runs `forge-triage ls --json`
- **THEN** the system SHALL output all notifications as a JSON array for programmatic consumption

#### Scenario: Empty inbox
- **WHEN** the user runs `forge-triage ls` with no notifications
- **THEN** the system SHALL print a message indicating the inbox is empty

### Requirement: Show notification stats
The system SHALL provide a CLI subcommand to display summary statistics.

#### Scenario: Stats output
- **WHEN** the user runs `forge-triage stats`
- **THEN** the system SHALL display: total notification count, count per priority tier, count per repo, and count per reason type

### Requirement: Raw SQL query interface
The system SHALL provide a CLI subcommand to execute arbitrary SQL queries against the local SQLite cache. This enables scripts and LLMs to perform custom triage logic.

#### Scenario: Execute a SQL query
- **WHEN** the user runs `forge-triage sql "SELECT repo_name, count(*) FROM notifications GROUP BY repo_name"`
- **THEN** the system SHALL execute the query against the database and print the results as a formatted table

#### Scenario: SQL query with JSON output
- **WHEN** the user runs `forge-triage sql --json "SELECT * FROM notifications WHERE priority_tier = 'blocking'"`
- **THEN** the system SHALL output the query results as a JSON array of objects

#### Scenario: SQL query with no results
- **WHEN** the user runs a SQL query that returns no rows
- **THEN** the system SHALL print an empty table (with headers) or an empty JSON array

#### Scenario: Invalid SQL
- **WHEN** the user runs `forge-triage sql "INVALID SQL"`
- **THEN** the system SHALL print the SQLite error message and exit with a non-zero status code

#### Scenario: Write operations blocked by default
- **WHEN** the user runs a SQL query containing INSERT, UPDATE, DELETE, or DROP
- **THEN** the system SHALL reject the query with an error message, unless `--write` flag is explicitly passed

### Requirement: Mark done from CLI
The system SHALL provide a CLI subcommand to mark notifications as done without opening the TUI.

#### Scenario: Mark single notification done
- **WHEN** the user runs `forge-triage done NixOS/nixpkgs#12345`
- **THEN** the system SHALL mark that notification as read on GitHub and delete it from the local database

#### Scenario: Mark done by filter
- **WHEN** the user runs `forge-triage done --reason subscribed`
- **THEN** the system SHALL mark all notifications with reason `subscribed` as done on GitHub and delete them locally, printing how many were dismissed

### Requirement: Sync subcommand
The system SHALL provide the sync subcommand as the entry point for fetching notifications.

#### Scenario: Run sync
- **WHEN** the user runs `forge-triage sync`
- **THEN** the system SHALL fetch notifications from GitHub, update the local database, pre-load comments for top-priority items, and print a summary (N new, M updated, K total)

#### Scenario: Sync with verbose output
- **WHEN** the user runs `forge-triage sync -v`
- **THEN** the system SHALL print progress details including API calls made, rate limit remaining, and per-notification updates

## Testing

- **Snapshot tests**: Capture expected CLI output for `forge-triage ls`, `forge-triage stats`, and `forge-triage sql` commands against a pre-populated test database. Snapshots cover both table and JSON output formats to catch formatting regressions.
- **Integration tests**: Test full CLI workflows (`ls`, `stats`, `done`, `sql`) by invoking the CLI entry point against a real temporary SQLite database with realistic notification data. Verify both stdout output and resulting database state (e.g., `done` actually removes the notification and calls the GitHub API mock).
