## Why

GitHub's notification web interface is too slow and noisy for users with 100+ notifications per session. There is no fast way to triage, filter, or bulk-dismiss notifications. The existing UI forces opening each notification individually, making it impossible to process a high-volume inbox efficiently. We need a local-first tool with a fast TUI that treats notifications as a triageable inbox.

## What Changes

- New Python CLI + Textual TUI for triaging GitHub notifications
- Sync GitHub notifications into a local SQLite database (cache, not source of truth)
- GitHub API remains the single source of truth — no cross-machine sync needed, each machine rebuilds its cache independently
- Textual-based TUI with split-pane list + detail view for reading full comment threads
- Computed priority sorting: review-requested > mentioned > CI-failed > subscribed
- Pre-load comments for top N notifications on sync, lazy-load the rest on preview
- CLI with direct SQL query interface for script/LLM-driven triage
- Triage action: mark as done locally → writes back to GitHub API (mark read/done) immediately
- Authentication via `gh auth token` (zero config)
- Packaged as a Nix flake

## Capabilities

### New Capabilities

- `github-sync`: Fetching notifications from the GitHub API, storing them in SQLite, incremental updates, pre-loading comments for top-priority items, lazy-loading on demand, and writing triage actions (mark read/done) back to GitHub
- `tui-triage`: Textual-based TUI with split-pane layout (notification list + detail/comment view), keyboard navigation (j/k, d for done, o for open in browser), filtering by repo/reason/author/label, grouping by repo, bulk select and bulk dismiss, and highlight of new-since-last-viewed comments
- `priority-engine`: Computed priority scoring for notifications — ranking by urgency (blocking someone > action needed > FYI), sorting the inbox by priority by default, and exposing priority as a queryable field
- `cli-query`: CLI subcommands for listing, filtering, and querying notifications, including a raw SQL interface against the SQLite cache for use by scripts and LLMs

### Modified Capabilities

_(none — greenfield project)_

## Impact

- **Dependencies**: Python 3.13, Textual, httpx, argparse (stdlib), SQLite (stdlib), Nix flake
- **External APIs**: GitHub Notifications API, GitHub Pull Requests/Issues API, GitHub Reviews/Comments API — subject to rate limits (5000 req/hour)
- **Auth**: Requires `gh` CLI to be installed and authenticated
- **Systems**: Local SQLite DB stored under XDG data directory (`$XDG_DATA_HOME/forge-triage/`), disposable cache — no data loss if deleted
