## Why

The TUI currently shows priority tier icons (🔴🟡⚪) in the first column of the notification list. While priority determines sort order, the tier icon doesn't convey actionable information at a glance — users can already infer priority from position. Showing the issue/PR state (open, closed, merged) as a nerdfont icon would give users immediately useful context: whether a PR was merged, an issue was closed, or something still needs attention, without having to open each notification.

## What Changes

- Replace the per-notification REST API calls (`fetch_ci_status`: 2 calls per PR) with a batched GraphQL query that fetches subject state, merged status, and CI status for all PR and Issue notifications in 1-2 round-trips
- Fetch and store the subject state (open, closed, merged) for Issue and PullRequest notifications during sync
- Add a `subject_state` column to the notifications table in the database schema
- Replace the priority tier indicator in the TUI notification list's first column with a nerdfont icon representing the subject state (e.g., `` for open issue, `` for closed issue, `` for open PR, `` for merged PR, `` for closed PR)
- For notification types that don't have a state (e.g., Release, Discussion), show a neutral icon
- Purge stale notifications from the local DB that GitHub no longer returns during sync, to prevent showing outdated state icons for notifications that have been dismissed or aged out

## Capabilities

### New Capabilities

- `subject-state`: Fetching, storing, and displaying issue/PR state (open, closed, merged) as nerdfont icons in the TUI

### Modified Capabilities

- `github-sync`: Sync must fetch subject state via GraphQL and purge stale notifications not returned by GitHub
- `tui-triage`: The notification list first column changes from priority tier icons to subject state nerdfont icons

## Impact

- **Database schema**: New `subject_state TEXT` column on the `notifications` table — existing databases need a migration or schema update
- **Sync**: Replaces per-PR REST calls with batched GraphQL, significantly reducing total API calls during sync. Adds `fetch_subject_details` GraphQL function, removes `fetch_ci_status` REST function
- **TUI**: `NotificationList` widget changes indicator rendering; snapshot tests will need updating
- **Priority engine**: Unaffected — priority still determines sort order, just no longer displayed as an icon
