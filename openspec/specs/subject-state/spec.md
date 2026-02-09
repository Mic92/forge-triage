## ADDED Requirements

### Requirement: Store subject state in the database
The system SHALL store the subject's state (open, closed, merged) in the notifications table as a `subject_state TEXT` column.

#### Scenario: PullRequest with open state
- **WHEN** a notification has `subject_type = "PullRequest"` and the PR resource has `state = "open"`
- **THEN** the `subject_state` column SHALL be set to `"open"`

#### Scenario: PullRequest merged
- **WHEN** a notification has `subject_type = "PullRequest"` and the PR resource has `state = "closed"` and `merged = true`
- **THEN** the `subject_state` column SHALL be set to `"merged"`

#### Scenario: PullRequest closed without merge
- **WHEN** a notification has `subject_type = "PullRequest"` and the PR resource has `state = "closed"` and `merged = false`
- **THEN** the `subject_state` column SHALL be set to `"closed"`

#### Scenario: Issue with open state
- **WHEN** a notification has `subject_type = "Issue"` and the Issue resource has `state = "open"`
- **THEN** the `subject_state` column SHALL be set to `"open"`

#### Scenario: Issue with closed state
- **WHEN** a notification has `subject_type = "Issue"` and the Issue resource has `state = "closed"`
- **THEN** the `subject_state` column SHALL be set to `"closed"`

#### Scenario: Unsupported subject type
- **WHEN** a notification has a subject type other than "PullRequest" or "Issue" (e.g., Release, Discussion)
- **THEN** the `subject_state` column SHALL be `NULL`

#### Scenario: Subject URL is null
- **WHEN** a notification has `subject.url = null` regardless of subject type
- **THEN** the `subject_state` column SHALL be `NULL`

### Requirement: Version-tracked schema migrations
The system SHALL track the database schema version and apply migrations sequentially on initialization.

#### Scenario: Fresh database
- **WHEN** the database is created for the first time
- **THEN** the notifications table SHALL include the `subject_state TEXT` column in its schema, and the `sync_metadata` table SHALL contain `schema_version` set to the latest version

#### Scenario: Legacy database without schema version
- **WHEN** the database exists but has no `schema_version` entry in `sync_metadata`
- **THEN** the system SHALL treat the current version as 0 and apply all migrations in order

#### Scenario: Migration adds subject_state column
- **WHEN** the database is at schema version 0 (pre-migration)
- **THEN** migration 1 SHALL add the `subject_state TEXT` column to the notifications table via `ALTER TABLE`, with existing rows having `subject_state = NULL`, and update `schema_version` to 1

#### Scenario: Database already at latest version
- **WHEN** the database `schema_version` matches the latest migration version
- **THEN** no migrations SHALL be applied

#### Scenario: Multiple pending migrations
- **WHEN** the database is behind by more than one version
- **THEN** the system SHALL apply each pending migration in version order

### Requirement: Display subject state as nerdfont icon
The system SHALL render the subject state as a nerdfont Octicon in the notification list's first column.

#### Scenario: Open issue
- **WHEN** a notification has `subject_type = "Issue"` and `subject_state = "open"`
- **THEN** the first column SHALL display the nerdfont `nf-oct-issue_opened` icon in green

#### Scenario: Closed issue
- **WHEN** a notification has `subject_type = "Issue"` and `subject_state = "closed"`
- **THEN** the first column SHALL display the nerdfont `nf-oct-issue_closed` icon in purple

#### Scenario: Open pull request
- **WHEN** a notification has `subject_type = "PullRequest"` and `subject_state = "open"`
- **THEN** the first column SHALL display the nerdfont `nf-oct-git_pull_request` icon in green

#### Scenario: Merged pull request
- **WHEN** a notification has `subject_type = "PullRequest"` and `subject_state = "merged"`
- **THEN** the first column SHALL display the nerdfont `nf-oct-git_merge` icon in purple

#### Scenario: Closed pull request (not merged)
- **WHEN** a notification has `subject_type = "PullRequest"` and `subject_state = "closed"`
- **THEN** the first column SHALL display the nerdfont `nf-oct-git_pull_request_closed` icon in red

#### Scenario: Unknown or null state
- **WHEN** a notification has `subject_state = NULL` or an unrecognized subject type
- **THEN** the first column SHALL display the nerdfont `nf-oct-bell` icon in dim/grey

## Testing

- **Integration tests (sync + DB)**: Run a full sync against recorded API responses containing PRs in open/closed/merged states and Issues in open/closed states. Verify the `subject_state` column values in the real SQLite database match expectations.
- **Integration tests (migration)**: Create a database with the old schema (no `subject_state` column, no `schema_version`), run `init_db`, and verify: the column is added, existing rows have `subject_state = NULL`, and `schema_version` is set to the latest version. Also test that running `init_db` again on an already-migrated DB is a no-op.
- **TUI snapshot tests**: Render the notification list with notifications in each state variant and snapshot the output to verify correct icons and colors.
- **TUI integration tests**: Use `App.run_test()` with a pre-populated SQLite DB containing all state combinations and verify the correct icon appears in the first column of each row.
