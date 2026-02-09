## ADDED Requirements

### Requirement: Fetch PR metadata
The system SHALL fetch PR metadata (author, description body, labels, base/head refs) from the GitHub API and cache it in the local database.

#### Scenario: Fetching PR metadata for a notification
- **WHEN** the user opens the detail view for a PR notification
- **THEN** the system SHALL fetch the PR's author login, body (description), labels, base ref, and head ref via the GitHub API and store them in the `pr_details` table keyed by notification_id

#### Scenario: PR metadata already cached
- **WHEN** the user opens the detail view for a PR whose metadata is already cached
- **THEN** the system SHALL display the cached metadata without making an API call

#### Scenario: Refreshing PR metadata
- **WHEN** the user presses `r` in the detail view
- **THEN** the system SHALL re-fetch PR metadata from the API and update the cache

### Requirement: Fetch PR review threads via GraphQL
The system SHALL fetch PR review threads, reviews, and review comments using the GitHub GraphQL API. The query SHALL retrieve threaded conversation structure, resolution state, and inline code context in a single query.

#### Scenario: Fetching review threads
- **WHEN** the Conversations tab is activated for the first time
- **THEN** the system SHALL execute a GraphQL query fetching the PR's review threads with: thread ID, resolution state (`isResolved`), and each comment's author, body, creation timestamp, associated file path, line number, and diff hunk context

#### Scenario: Fetching reviews (approvals, change requests)
- **WHEN** the Conversations tab is activated
- **THEN** the system SHALL also fetch PR reviews (approve, request_changes, comment) with: review ID, author, state, body, and submission timestamp

#### Scenario: Pagination of review threads
- **WHEN** the PR has more review threads than the per-query limit (100 threads)
- **THEN** the system SHALL paginate using cursor-based pagination, fetching subsequent pages until all threads are retrieved

#### Scenario: Caching review data
- **WHEN** review threads and reviews are fetched
- **THEN** the system SHALL store them in the `pr_reviews` and `review_comments` tables, including the `is_resolved` flag on each comment's thread

### Requirement: Fetch PR changed files via REST
The system SHALL fetch the list of changed files for a PR using the GitHub REST API (`GET /repos/{owner}/{repo}/pulls/{number}/files`). The response includes filename, change status, line counts, and patch text for each file.

#### Scenario: Fetching changed files
- **WHEN** the Files Changed tab is activated for the first time
- **THEN** the system SHALL fetch the PR's changed files via REST and store filename, status (added/modified/deleted/renamed), additions count, deletions count, and patch text in the `pr_files` table

#### Scenario: Pagination of changed files
- **WHEN** the PR has more than 100 changed files (GitHub's per-page limit)
- **THEN** the system SHALL paginate using the Link header, fetching all pages

#### Scenario: File with no patch
- **WHEN** a changed file has no `patch` field in the API response (binary file or too large)
- **THEN** the system SHALL store the file record with a NULL patch and set a flag indicating no diff is available

### Requirement: Post reply to review thread
The system SHALL post a reply comment to an existing review conversation thread via the GitHub REST API.

#### Scenario: Posting a reply
- **WHEN** the user submits a reply to a review thread
- **THEN** the system SHALL POST the comment body to `POST /repos/{owner}/{repo}/pulls/{number}/comments/{comment_id}/replies` and update the local cache with the new comment

#### Scenario: Reply authentication
- **WHEN** a reply is posted
- **THEN** the system SHALL use the token obtained from `gh auth token` as a Bearer token

#### Scenario: Reply failure
- **WHEN** the GitHub API returns an error (403, 404, 422)
- **THEN** the system SHALL return an error result with the HTTP status and error message from the response body

### Requirement: Submit PR review (approve or request changes)
The system SHALL submit a PR review via the GitHub REST API (`POST /repos/{owner}/{repo}/pulls/{number}/reviews`).

#### Scenario: Submitting an approval
- **WHEN** the user approves a PR
- **THEN** the system SHALL POST a review with `event: "APPROVE"` and an empty body

#### Scenario: Submitting a change request
- **WHEN** the user requests changes with a review body
- **THEN** the system SHALL POST a review with `event: "REQUEST_CHANGES"` and the user-provided body

#### Scenario: Review submission failure
- **WHEN** submitting a review fails
- **THEN** the system SHALL return an error result with the HTTP status and error message

### Requirement: Resolve and unresolve review threads
The system SHALL resolve and unresolve review conversation threads via the GitHub GraphQL API using the `resolveReviewThread` and `unresolveReviewThread` mutations.

#### Scenario: Resolving a thread
- **WHEN** the user resolves a review thread
- **THEN** the system SHALL execute the `resolveReviewThread` GraphQL mutation with the thread's node ID and update the local cache to mark the thread as resolved

#### Scenario: Unresolving a thread
- **WHEN** the user unresolves a review thread
- **THEN** the system SHALL execute the `unresolveReviewThread` GraphQL mutation with the thread's node ID and update the local cache to mark the thread as unresolved

#### Scenario: Resolve/unresolve failure
- **WHEN** the GraphQL mutation returns an error
- **THEN** the system SHALL return an error result with the error message from the GraphQL response

### Requirement: PR data caching in local database
The system SHALL cache all fetched PR data in SQLite tables to avoid redundant API calls. The schema SHALL include tables for PR details, reviews, review comments, and changed files.

#### Scenario: Database schema for PR data
- **WHEN** the database is initialized
- **THEN** the system SHALL create tables: `pr_details` (notification_id FK, pr_number, author, body, labels_json, base_ref, head_ref, loaded_at), `pr_reviews` (review_id PK, notification_id FK, author, state, body, submitted_at), `review_comments` (comment_id PK, review_id FK, notification_id FK, author, body, path, diff_hunk, line, side, in_reply_to_id, is_resolved, created_at, updated_at), `pr_files` (file_id PK, notification_id FK, filename, status, additions, deletions, patch)

#### Scenario: Cascade deletion
- **WHEN** a notification is deleted from the `notifications` table
- **THEN** all associated PR data (pr_details, pr_reviews, review_comments, pr_files) SHALL be cascade-deleted

#### Scenario: Cache invalidation on refresh
- **WHEN** the user refreshes the detail view
- **THEN** the system SHALL delete existing cached data for that notification and re-fetch from the API

### Requirement: Async message types for PR operations
The system SHALL define request/response message types for PR data operations, following the existing async queue pattern used by the backend worker.

#### Scenario: FetchPRDetailRequest and result
- **WHEN** the detail view needs PR data
- **THEN** it SHALL post a `FetchPRDetailRequest` with the notification_id to the request queue. The backend SHALL respond with a `FetchPRDetailResult` containing success/failure status.

#### Scenario: PostReviewCommentRequest and result
- **WHEN** the user submits a reply
- **THEN** the TUI SHALL post a `PostReviewCommentRequest` with notification_id, thread_id, and body. The backend SHALL respond with `PostReviewCommentResult`.

#### Scenario: SubmitReviewRequest and result
- **WHEN** the user approves or requests changes
- **THEN** the TUI SHALL post a `SubmitReviewRequest` with notification_id, event (APPROVE/REQUEST_CHANGES), and optional body. The backend SHALL respond with `SubmitReviewResult`.

#### Scenario: ResolveThreadRequest and result
- **WHEN** the user resolves or unresolves a thread
- **THEN** the TUI SHALL post a `ResolveThreadRequest` with notification_id, thread_node_id, and resolve (bool). The backend SHALL respond with `ResolveThreadResult`.

## Testing

- **GraphQL query construction tests**: Test that the review threads query is correctly constructed with pagination cursors. Test with PRs having varying numbers of review threads (0, 1, 100+).
- **GraphQL response parsing tests**: Test parsing of review threads, reviews, and comments from canned GraphQL responses. Test partial failures (some threads return errors).
- **REST API tests**: Test PR file fetching with canned REST responses including pagination. Test files with and without patch data.
- **Mutation tests**: Test approve, request changes, reply, resolve, and unresolve mutations with mocked API responses. Test error responses (403, 404, 422).
- **Database tests**: Test all CRUD operations on the new tables with in-memory SQLite. Test cascade deletion. Test cache invalidation on refresh. Test schema migrations from the previous version.
- **Message type tests**: Test that each request/response message round-trips through the backend worker correctly with mocked API calls.
