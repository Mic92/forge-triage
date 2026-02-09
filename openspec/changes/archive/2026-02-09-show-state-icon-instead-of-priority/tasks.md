## 1. Schema Migration System

- [x] 1.1 Write failing integration test for legacy DB migration + implement migration system in `db.py`

## 2. GraphQL Subject Details Fetcher

- [x] 2.1 Implement `parse_subject_url`, `_build_subject_details_query`, `_parse_graphql_response`, and `fetch_subject_details` in `github.py`. Write one integration test for `fetch_subject_details` that mocks HTTP with canned GraphQL responses covering: open PR, merged PR, closed PR, open issue, closed issue across two repos, plus partial errors (failed nodes → `(None, None)`)

## 3. Sync: Replace REST with GraphQL for Subject Details

- [x] 3.1 Update `_notification_to_row`, `upsert_notification`, and `sync()` to use `fetch_subject_details` instead of per-notification `fetch_ci_status`. Remove `fetch_ci_status`. Write one sync integration test with mixed notifications validating `subject_state` and `ci_status` in DB
- [x] 3.2 Update `NotificationRow` in conftest and fix all existing tests broken by the schema/sync changes

## 4. Purge Stale Notifications

- [x] 4.1 Implement stale purge in `sync.py` + write integration tests: basic purge (older notifications deleted, newer kept, `purged` count correct) and empty sync response (all deleted)

## 5. TUI: Replace Priority Icon with State Icon

- [x] 5.1 Replace `_TIER_INDICATORS` with `_state_icon(subject_type, subject_state)` in `notification_list.py`, update `refresh_data` to use it. Write TUI integration test with all state variants

## 6. Final Validation

- [x] 6.1 Run `ruff format`, `ruff check`, `mypy` across the entire codebase and fix all issues
- [x] 6.2 Run the full test suite and verify all tests pass
