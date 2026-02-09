## MODIFIED Requirements

### Requirement: Fetch notifications from GitHub API
The system SHALL fetch the authenticated user's notifications from the GitHub Notifications API, then batch-fetch subject details (state, merged status, CI status) via the GitHub GraphQL API, and store everything in a local SQLite database.

#### Scenario: Initial sync with no local data
- **WHEN** the user runs `forge-triage sync` for the first time
- **THEN** the system SHALL fetch all unread notifications from GitHub via REST, then batch-fetch subject details (state, merged, CI status) for all PR and Issue notifications via a single GraphQL query, and insert them into the SQLite database with fields: notification_id, repo_owner, repo_name, subject_type, subject_title, subject_url, reason, updated_at, unread status, subject_state, ci_status, and raw JSON payload

#### Scenario: Incremental sync
- **WHEN** the user runs `forge-triage sync` and the database already contains notifications
- **THEN** the system SHALL fetch only notifications updated since the last sync timestamp (using `since` parameter) via REST, batch-fetch subject details via GraphQL, and upsert them into the database including the current subject_state and ci_status

#### Scenario: Batch GraphQL query for subject details
- **WHEN** notifications have been fetched via REST
- **THEN** the system SHALL construct a single GraphQL query that groups subjects by repository, using aliases, to fetch PR state/merged/CI status and Issue state in one round-trip

#### Scenario: GraphQL batching for large notification counts
- **WHEN** the number of subjects exceeds the GraphQL complexity limit (~500 nodes)
- **THEN** the system SHALL split subjects into multiple GraphQL queries and execute them sequentially

#### Scenario: Subject URL is null
- **WHEN** a notification has `subject.url = null`
- **THEN** the system SHALL exclude it from the GraphQL batch and set `subject_state = NULL` and `ci_status = NULL`

#### Scenario: GraphQL partial failure
- **WHEN** the GraphQL response contains errors for some nodes (e.g., deleted PR, private repo)
- **THEN** the system SHALL set `subject_state = NULL` and `ci_status = NULL` for the failed nodes and continue processing the successful ones

#### Scenario: Unsupported subject type
- **WHEN** a notification has a subject type other than "PullRequest" or "Issue"
- **THEN** the system SHALL exclude it from the GraphQL batch and set `subject_state = NULL`

#### Scenario: GitHub API authentication
- **WHEN** the system needs to authenticate with GitHub
- **THEN** it SHALL obtain the token by executing `gh auth token` and use it as a Bearer token for both REST and GraphQL API requests

#### Scenario: Authentication failure
- **WHEN** `gh auth token` fails or returns an empty token
- **THEN** the system SHALL exit with a clear error message explaining that `gh` CLI must be installed and authenticated

### Requirement: Purge stale notifications
The system SHALL remove local notifications that GitHub no longer returns, to prevent showing outdated state information.

#### Scenario: Notification no longer returned by GitHub
- **WHEN** a sync completes and a local notification's `notification_id` was not in the set returned by GitHub AND its `updated_at` is older than or equal to the oldest `updated_at` in the fetched batch
- **THEN** the system SHALL delete that notification and its associated comments from the local database

#### Scenario: Notification absent due to incremental sync window
- **WHEN** a sync completes and a local notification was not returned but its `updated_at` is newer than the oldest `updated_at` in the fetched batch
- **THEN** the system SHALL keep that notification (it may simply be unchanged since the last sync)

#### Scenario: Empty sync response
- **WHEN** a sync returns zero notifications (e.g., inbox is empty)
- **THEN** the system SHALL delete all local notifications since GitHub confirms none exist

#### Scenario: Sync result reports purged count
- **WHEN** notifications are purged during sync
- **THEN** the `SyncResult` SHALL include the count of purged notifications

## REMOVED Requirements

### Requirement: Respect GitHub API rate limits
**Reason**: The existing REST-based rate limit handling (`X-RateLimit-Remaining` header, HTTP 403 detection) is specific to REST API responses. GraphQL uses a different point-based rate limit system. The rate limit handling needs to be rewritten for GraphQL.
**Migration**: Replace with GraphQL-aware rate limit handling that checks the `rateLimit` field in GraphQL responses and the REST rate limit headers for the notifications endpoint.

## ADDED Requirements

### Requirement: Respect GitHub API rate limits
The system SHALL handle rate limiting for both REST (notifications endpoint) and GraphQL (subject details) APIs.

#### Scenario: REST rate limit approaching
- **WHEN** the `X-RateLimit-Remaining` header on a REST response indicates fewer than 100 remaining requests
- **THEN** the system SHALL log a warning with the reset time

#### Scenario: REST rate limit exceeded
- **WHEN** the REST API returns HTTP 403 with rate limit exceeded
- **THEN** the system SHALL stop making requests, report the remaining wait time to the user, and exit gracefully with the data fetched so far

#### Scenario: GraphQL rate limit information
- **WHEN** a GraphQL response is received
- **THEN** the system SHALL check the `rateLimit` field for remaining points and log a warning if below a threshold

#### Scenario: GraphQL rate limit exceeded
- **WHEN** the GraphQL API returns a rate limit error
- **THEN** the system SHALL stop making GraphQL requests, set `subject_state = NULL` and `ci_status = NULL` for unfetched subjects, and continue with the data fetched so far

## Testing

- **Integration tests (GraphQL)**: Test the batched GraphQL fetch with canned HTTP responses containing PRs (open, closed, merged with varying CI status) and Issues (open, closed) grouped across multiple repositories. Verify correct parsing of state, merged, and CI status. Test batching behavior when notification count exceeds the per-query limit.
- **Integration tests (full sync flow)**: Test the end-to-end sync with recorded REST responses for notifications and canned GraphQL responses for subject details. Verify `subject_state` and `ci_status` are correctly stored in a real SQLite database.
- **Integration tests (error handling)**: Test sync when GraphQL returns partial errors (some nodes fail). Verify failed nodes get `subject_state = NULL` and successful ones are stored correctly.
- **Integration tests (null/unsupported subjects)**: Include notifications with `subject.url = null` and non-PR/Issue types. Verify they are excluded from GraphQL batch and stored with `subject_state = NULL`.
- **Integration tests (rate limits)**: Test both REST and GraphQL rate limit handling by simulating rate limit responses.
- **Integration tests (stale purge)**: Pre-populate DB with notifications, run sync with a subset returned by GitHub. Verify notifications older than the oldest returned one are deleted. Verify notifications newer than the cutoff are kept. Test empty sync response purges all. Verify `SyncResult.purged` count is correct.
