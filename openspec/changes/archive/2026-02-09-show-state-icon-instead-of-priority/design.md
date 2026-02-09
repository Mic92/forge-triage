## Context

The TUI notification list currently renders a priority tier icon (🔴🟡⚪) in the first column. Priority determines sort order, so position already communicates urgency. The first column would be more useful showing the subject's state (open/closed/merged), giving users immediate context about whether action is still possible.

The GitHub Notifications API does not include the subject's state directly. The `subject.url` field points to the Issue or PR API resource, which must be fetched separately. However, `fetch_ci_status` already fetches the PR resource to extract the head SHA for CI status — the `state` and `merged` fields are present in that same response.

Current relevant code:
- `src/forge_triage/db.py` — Schema with `notifications` table (no `subject_state` column)
- `src/forge_triage/sync.py` — Sync loop calls `fetch_ci_status` for PRs, which already fetches the PR resource
- `src/forge_triage/github.py` — `fetch_ci_status` fetches PR data but discards the state
- `src/forge_triage/tui/notification_list.py` — Renders `_TIER_INDICATORS` dict in first column

## Goals / Non-Goals

**Goals:**
- Show subject state (open, closed, merged) as nerdfont icons in the TUI notification list
- Fetch and persist subject state during sync with minimal additional API calls
- Handle all notification subject types gracefully (Issue, PullRequest, Release, Discussion, etc.)

**Non-Goals:**
- Changing priority computation or sort order (priority still drives sorting)
- Real-time state updates outside of sync (state is only refreshed on `forge-triage sync`)
- Showing both priority tier AND state icon (only state icon replaces priority icon)

## Decisions

### Decision 1: Batch-fetch subject details via GitHub GraphQL API

**Choice**: Replace the per-notification REST calls (`fetch_ci_status` doing 2 REST calls per PR) with a single batched GraphQL query that fetches subject state, merged status, and CI status for all PR and Issue notifications at once.

The GraphQL query uses repository-scoped lookups with aliases to fetch multiple subjects in one request:

```graphql
query {
  r0: repository(owner: "NixOS", name: "nixpkgs") {
    pr123: pullRequest(number: 123) {
      state
      merged
      commits(last: 1) { nodes { commit { statusCheckRollup { state } } } }
    }
    issue456: issue(number: 456) {
      state
    }
  }
  r1: repository(owner: "other", name: "repo") {
    ...
  }
}
```

This groups subjects by repository and uses aliases (`r0`, `pr123`, `issue456`) to fetch everything in one round-trip. The query handles up to ~500 nodes per request (GitHub's GraphQL complexity limit); if more are needed, batch into multiple queries.

**Rationale**: The current approach makes 2 REST calls per PR (GET PR + GET commit status) and would add 1 more per Issue. For 50 notifications with 30 PRs and 20 Issues, that's 80 REST calls → 1-2 GraphQL calls. This dramatically reduces API usage and sync time.

**Alternatives considered**:
- Per-notification REST calls (current approach + extensions) — O(N) API calls, slow for large notification counts, wastes rate limit budget.
- Refactor `fetch_ci_status` to also return state — still O(N) calls, just extracts more data per call.

### Decision 2: Parse subject owner/repo/number from notification subject URL

**Choice**: Extract the repository owner, name, and issue/PR number from the `subject.url` field (e.g., `https://api.github.com/repos/NixOS/nixpkgs/pulls/12345` → owner=`NixOS`, name=`nixpkgs`, number=`12345`, type=`PullRequest`). Group by repository for the GraphQL query.

**Rationale**: The notification payload already has `repository.owner.login`, `repository.name`, and the number can be parsed from `subject.url`. This avoids any extra API calls just to identify the subject.

**Alternatives considered**:
- Use `subject.url` directly with REST — can't batch.
- Store owner/repo/number separately — the URL parsing is trivial and already partially done in `_notification_to_row`.

### Decision 3: Purge stale notifications after sync

**Choice**: After each sync, delete local notifications whose `notification_id` was not in the fetched set AND whose `updated_at` is older than or equal to the oldest `updated_at` in the fetched batch. If the sync returns zero notifications, delete all local notifications.

**Rationale**: Showing state icons makes staleness much more visible — a PR showing "open" weeks after it was merged is actively misleading. The current sync upserts but never deletes, so notifications that GitHub no longer returns (dismissed elsewhere, aged out, or cut off by the 1000-notification cap) accumulate indefinitely. The `updated_at` cutoff ensures we only purge notifications that fall within the time window the API covered, so incremental syncs don't accidentally purge unchanged-but-valid notifications.

**Alternatives considered**:
- Purge only on full sync (no `since` param) — would require tracking sync mode, and incremental syncs could still accumulate stale entries from the cap.
- TTL-based expiry — arbitrary, doesn't reflect GitHub's actual notification state.
- Never purge (current behavior) — acceptable when showing priority icons, unacceptable when showing state icons that go stale.

### Decision 4: Use a single `subject_state` TEXT column

**Choice**: Add `subject_state TEXT` column to the notifications table with values: `"open"`, `"closed"`, `"merged"`, or `NULL` (for unsupported subject types like Release, Discussion).

**Rationale**: A single column is simple and sufficient. PRs map to open/closed/merged (where "merged" is derived from `state == "closed" AND merged == true`). Issues map to open/closed. Other types get NULL.

### Decision 5: Nerdfont icon mapping

**Choice**: Map subject state + subject type to nerdfont icons:

| Subject Type  | State    | Icon | Nerdfont Name            | Color   |
|---------------|----------|------|--------------------------|---------|
| Issue         | open     |    | `nf-oct-issue_opened`    | green   |
| Issue         | closed   |    | `nf-oct-issue_closed`    | purple  |
| PullRequest   | open     |    | `nf-oct-git_pull_request`| green   |
| PullRequest   | merged   |    | `nf-oct-git_merge`       | purple  |
| PullRequest   | closed   |    | `nf-oct-git_pull_request_closed` | red |
| Other/NULL    | —        |    | `nf-oct-bell`            | dim     |

**Rationale**: These match GitHub's own iconography (Octicons). Colors follow GitHub conventions (green=open, purple=merged/closed-achieved, red=closed-unmerged). Nerdfont Octicons are the natural choice since they're GitHub's icon set.

**Alternatives considered**:
- Unicode emoji (🟢🔴🟣) — less recognizable, no type distinction between Issue and PR.
- Plain text labels ("open", "merged") — takes more column width.

### Decision 6: Version-tracked schema migration system

**Choice**: Introduce a schema version tracking system. Store the current schema version in the `sync_metadata` table (key: `schema_version`). On `init_db`, check the current version and apply migrations sequentially up to the target version. Each migration is a function that takes a connection and applies the necessary DDL. Fresh databases get the full up-to-date schema and are stamped with the latest version.

Migration flow:
1. `init_db` creates tables if they don't exist (fresh DB gets full schema + latest version stamp)
2. Read `schema_version` from `sync_metadata` (default 0 if absent = legacy DB)
3. Apply each migration where `migration.version > current_version` in order
4. Update `schema_version` to latest

Migration 1 (version 0 → 1): `ALTER TABLE notifications ADD COLUMN subject_state TEXT`

**Rationale**: While the DB is disposable, a proper migration system is low-effort and avoids ad-hoc `try/except ALTER TABLE` hacks. It scales cleanly for future schema changes and makes the upgrade path explicit and testable. Using the existing `sync_metadata` table avoids adding new tables.

**Alternatives considered**:
- Ad-hoc `ALTER TABLE` with try/except — doesn't scale, no visibility into what version the DB is at.
- Formal migration framework (alembic) — overkill for a disposable cache DB with simple DDL changes.
- Drop and recreate — loses cached data unnecessarily.

## Risks / Trade-offs

- **[GraphQL complexity limits]** → GitHub limits GraphQL queries to ~500 nodes. Mitigated by: batching into multiple queries if notification count exceeds the limit. In practice, most users have far fewer notifications.
- **[GraphQL rate limiting differs from REST]** → GraphQL uses a point-based system (5000 points/hour) rather than request count. Mitigated by: each query costs ~1 point per node, so even 500 notifications costs ~500 points — well within budget.
- **[Stale state between syncs]** → Subject state is only refreshed on sync. A PR merged after the last sync will still show as "open" until next sync. Mitigated by: this matches the existing behavior for all notification data — users already run `sync` to refresh.
- **[subject.url can be NULL]** → Some notification types (e.g., security advisories) have `subject.url = null`. Mitigated by: these are excluded from the GraphQL batch and get `subject_state = NULL` with the neutral bell icon.
- **[Removes existing REST-based CI status fetch]** → `fetch_ci_status` is replaced entirely. Mitigated by: GraphQL `statusCheckRollup` provides equivalent data. Tests cover the same CI status scenarios.

## Testing Strategy

- **Integration tests (GraphQL)**: Test the batched GraphQL fetch function with canned HTTP responses. Verify correct parsing of state, merged, and CI status for PRs and Issues grouped by repository. Test batching behavior when notification count exceeds the per-query limit. Test error handling for partial GraphQL responses (some nodes fail).
- **Integration tests (real SQLite)**: Test the full sync flow with recorded API responses (REST for notifications, GraphQL for subject details). Verify `subject_state` and `ci_status` are correctly stored in the database.
- **Integration tests (URL parsing)**: Test extraction of owner/repo/number from various `subject.url` formats including edge cases (null URLs, unexpected formats).
- **TUI snapshot tests**: Update existing Textual snapshot tests to reflect the new icons in the first column. Add snapshots for each state variant (open issue, closed issue, open PR, merged PR, closed PR, unknown type).
- **TUI integration tests**: Use `App.run_test()` with a pre-populated SQLite DB containing notifications in various states. Verify the correct icon renders for each row.

## Open Questions

None — the approach is straightforward and all decisions are resolved.
