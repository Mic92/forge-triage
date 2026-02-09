## ADDED Requirements

### Requirement: Compute priority score for notifications
The system SHALL assign a numeric priority score to each notification based on its attributes. Higher scores indicate higher urgency.

#### Scenario: Review requested — CI passing
- **WHEN** a notification has reason `review_requested` and the associated PR has passing CI
- **THEN** it SHALL receive the highest priority tier (blocking someone)

#### Scenario: Review requested — CI failing
- **WHEN** a notification has reason `review_requested` and the associated PR has failing CI
- **THEN** it SHALL receive a lower priority than review-requested-with-passing-CI (the author needs to fix CI first)

#### Scenario: Mentioned or assigned
- **WHEN** a notification has reason `mention` or `assign`
- **THEN** it SHALL receive the second priority tier (action needed)

#### Scenario: CI failure on user's own PR
- **WHEN** a notification is for a PR authored by the authenticated user and CI has failed
- **THEN** it SHALL receive the second priority tier (action needed)

#### Scenario: Subscribed or team mention
- **WHEN** a notification has reason `subscribed` or `team_mention`
- **THEN** it SHALL receive the lowest priority tier (FYI)

#### Scenario: Recency as tiebreaker
- **WHEN** two notifications have the same priority tier
- **THEN** the more recently updated notification SHALL sort first

### Requirement: Priority tiers
The system SHALL define three priority tiers with clear labels for display.

#### Scenario: Display priority tiers
- **WHEN** a notification is displayed in the TUI or CLI output
- **THEN** its priority tier SHALL be shown as one of: 🔴 Blocking (you're blocking someone), 🟡 Action (you need to act), ⚪ FYI (informational)

### Requirement: Priority is queryable
The system SHALL store the computed priority score and tier in the SQLite database so it can be queried via SQL.

#### Scenario: Priority columns in database
- **WHEN** a notification is stored or updated
- **THEN** the notifications table SHALL contain columns `priority_score` (integer) and `priority_tier` (text: "blocking", "action", "fyi")

#### Scenario: Querying by priority via SQL
- **WHEN** a user or script queries `SELECT * FROM notifications ORDER BY priority_score DESC`
- **THEN** the results SHALL be ordered from most urgent to least urgent

### Requirement: Priority recalculation on sync
The system SHALL recalculate priority scores whenever notifications are synced.

#### Scenario: Priority update after sync
- **WHEN** a notification's attributes change during sync (e.g., CI status changes from failing to passing)
- **THEN** the system SHALL recalculate and update its priority score and tier

## Testing

- **Integration tests**: Test priority scoring through the full sync flow — insert notifications with various reasons and CI statuses into a real SQLite database via the sync engine, then verify the resulting `priority_score` and `priority_tier` columns produce the correct ordering.
- **Snapshot tests**: Capture the sorted notification list output (via `forge-triage ls`) for a fixture set of notifications spanning all priority tiers, to catch ordering regressions.
- **Edge case coverage**: Include notifications with missing CI status, unknown reason types, and issues (not PRs) in the integration test fixtures.
