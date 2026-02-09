## ADDED Requirements

### Requirement: Fetch notifications from GitHub API
The system SHALL fetch the authenticated user's notifications from the GitHub Notifications API and store them in a local SQLite database.

#### Scenario: Initial sync with no local data
- **WHEN** the user runs `forge-triage sync` for the first time
- **THEN** the system fetches all unread notifications from GitHub and inserts them into the SQLite database with fields: notification_id, repo_owner, repo_name, subject_type, subject_title, subject_url, reason, updated_at, unread status, and raw JSON payload

#### Scenario: Incremental sync
- **WHEN** the user runs `forge-triage sync` and the database already contains notifications
- **THEN** the system fetches only notifications updated since the last sync timestamp (using `If-Modified-Since` or `since` parameter) and upserts them into the database

#### Scenario: GitHub API authentication
- **WHEN** the system needs to authenticate with GitHub
- **THEN** it SHALL obtain the token by executing `gh auth token` and use it as a Bearer token for all API requests

#### Scenario: Authentication failure
- **WHEN** `gh auth token` fails or returns an empty token
- **THEN** the system SHALL exit with a clear error message explaining that `gh` CLI must be installed and authenticated

### Requirement: Store notifications in SQLite
The system SHALL use a SQLite database located at `$XDG_DATA_HOME/forge-triage/notifications.db` as a local cache. The database is disposable and rebuildable from GitHub at any time.

#### Scenario: Database creation
- **WHEN** the database file does not exist
- **THEN** the system SHALL create it with the required schema including tables for notifications, comments, and sync metadata

#### Scenario: XDG path resolution
- **WHEN** `$XDG_DATA_HOME` is set
- **THEN** the database SHALL be stored at `$XDG_DATA_HOME/forge-triage/notifications.db`

#### Scenario: XDG fallback
- **WHEN** `$XDG_DATA_HOME` is not set
- **THEN** the database SHALL be stored at `$HOME/.local/share/forge-triage/notifications.db`

### Requirement: Pre-load comments for top-priority notifications
The system SHALL fetch full comment threads for the top N highest-priority notifications during sync, where N is configurable (default: 20).

#### Scenario: Pre-loading comments on sync
- **WHEN** the user runs `forge-triage sync`
- **THEN** the system fetches comments for the top 20 notifications (by computed priority) and stores them in the comments table with fields: comment_id, notification_id, author, body, created_at, updated_at

#### Scenario: Skipping already-loaded comments
- **WHEN** comments for a notification have already been fetched and the notification's updated_at has not changed
- **THEN** the system SHALL skip re-fetching comments for that notification

#### Scenario: Invalidating comments on notification update
- **WHEN** a notification's `updated_at` has changed during sync and comments were previously loaded
- **THEN** the system SHALL set `comments_loaded` to 0, so the next preview triggers a re-fetch

### Requirement: Lazy-load comments on demand
The system SHALL provide a function to fetch comments for a specific notification on demand, for notifications not covered by pre-loading.

#### Scenario: Requesting comments for a notification without cached comments
- **WHEN** a caller requests comments for a notification that has no cached comments
- **THEN** the system fetches the full comment thread from GitHub, stores it in the database, and returns the comments

#### Scenario: Requesting comments for a notification with cached comments
- **WHEN** a caller requests comments for a notification that already has cached comments and the notification's updated_at has not changed
- **THEN** the system returns the cached comments without making an API call

### Requirement: Write triage actions back to GitHub
The system SHALL mark notifications as read/done on GitHub when the user triages them locally.

#### Scenario: Marking a notification as done
- **WHEN** the user marks a notification as done
- **THEN** the system SHALL call `PATCH /notifications/threads/{thread_id}` to mark it as read on GitHub and delete the notification from the local database

#### Scenario: Bulk marking notifications as done
- **WHEN** the user marks multiple notifications as done in a single action
- **THEN** the system SHALL mark each notification as read on GitHub and delete them from the local database

#### Scenario: GitHub API failure during triage
- **WHEN** the GitHub API call to mark a notification as read fails
- **THEN** the system SHALL report the error to the user and keep the notification in the local database (not delete it)

### Requirement: Respect GitHub API rate limits
The system SHALL handle GitHub API rate limiting gracefully.

#### Scenario: Rate limit approaching
- **WHEN** the `X-RateLimit-Remaining` header indicates fewer than 100 remaining requests
- **THEN** the system SHALL log a warning with the reset time

#### Scenario: Rate limit exceeded
- **WHEN** the API returns HTTP 403 with rate limit exceeded
- **THEN** the system SHALL stop making requests, report the remaining wait time to the user, and exit gracefully with the data fetched so far

## Testing

- **Integration tests**: Test the full sync flow (fetch → store → incremental update) against recorded GitHub API responses with a real temporary SQLite database. Cover initial sync, incremental sync, comment pre-loading, and comment lazy-loading end-to-end.
- **Snapshot tests**: Capture expected sync summary output and database state after sync operations to catch regressions.
- **Integration tests (auth)**: Test `gh auth token` integration with mocked subprocess for success, failure, and missing `gh` cases — verify the full auth → fetch flow, not just token parsing.
- **Integration tests (rate limits)**: Test rate limit handling by simulating API responses with rate limit headers through a full sync cycle, verifying graceful degradation.
