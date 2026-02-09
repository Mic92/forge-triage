## 1. Project scaffolding

- [ ] 1.1 Create `pyproject.toml` with project metadata, entry point (`forge-triage`), and dependencies (textual, httpx)
- [ ] 1.2 Create `flake.nix` with `buildPythonApplication`, devShell (python, ruff, mypy, pytest, pytest-httpx), and multi-platform support (x86_64-linux, aarch64-darwin)
- [ ] 1.3 Create package skeleton: `src/forge_triage/__init__.py`, `__main__.py`, and empty modules (`cli.py`, `db.py`, `github.py`, `priority.py`, `sync.py`, `messages.py`, `backend.py`, `tui/__init__.py`, `tui/app.py`)
- [ ] 1.4 Create `tests/conftest.py` with shared fixtures: temporary SQLite database, sample GitHub API notification JSON fixtures, mock `gh auth token` helper, fake backend (canned response queue for TUI tests)
- [ ] 1.5 Verify `nix build` produces a working `forge-triage` binary, `nix develop` provides all dev tools, `pytest` runs (even with zero tests)
- [ ] 1.6 Run `ruff format`, `ruff check`, `mypy --strict` — fix any issues

## 2. Database layer

- [ ] 2.1 Write integration test: create a DB, verify schema (tables `notifications`, `comments`, `sync_metadata` exist with correct columns), insert and query a notification
- [ ] 2.2 Implement `db.py`: `get_db_path()` (XDG resolution), `init_db()` (schema creation with WAL mode), connection helper
- [ ] 2.3 Write integration test: XDG path resolution — test with `$XDG_DATA_HOME` set, unset (fallback to `$HOME/.local/share/forge-triage/`)
- [ ] 2.4 Implement XDG path logic in `get_db_path()`
- [ ] 2.5 Write integration test: upsert notification — insert new, update existing (changed `updated_at`), verify idempotency
- [ ] 2.6 Write integration test: upsert with `updated_at` change resets `comments_loaded` to 0 — verify previously loaded comments are invalidated
- [ ] 2.7 Implement `upsert_notification()` and `delete_notification()` in `db.py` — upsert sets `comments_loaded = 0` when `updated_at` changes
- [ ] 2.8 Write integration test: comment storage — insert comments, query by notification_id ordered by created_at, verify cascade delete (delete notification → comments gone)
- [ ] 2.9 Implement `upsert_comments()` and `get_comments()` in `db.py`
- [ ] 2.10 Write integration test: sync metadata — store and retrieve `last_sync_at`, update it
- [ ] 2.11 Implement `get_sync_meta()` and `set_sync_meta()` in `db.py`
- [ ] 2.12 Run `ruff format`, `ruff check`, `mypy --strict` — fix any issues

## 3. GitHub API client

- [ ] 3.1 Write integration test: `get_github_token()` — mock `subprocess.run` for success (returns token), failure (non-zero exit), and empty output
- [ ] 3.2 Implement `get_github_token()` in `github.py`
- [ ] 3.3 Write integration test: fetch notifications — mock httpx responses with recorded GitHub API JSON, verify parsed notification list matches expected structure, test pagination (multiple pages via `Link` header)
- [ ] 3.4 Implement `fetch_notifications()` in `github.py` using `httpx.AsyncClient` with Bearer auth and `since` parameter
- [ ] 3.5 Write integration test: fetch comments for a PR — mock httpx with recorded comments JSON, verify parsed comments match expected structure
- [ ] 3.6 Implement `fetch_comments()` in `github.py` — resolve comment URL from notification subject, fetch and parse
- [ ] 3.7 Write integration test: fetch CI status for a PR — mock httpx with combined status JSON, verify parsed status
- [ ] 3.8 Implement `fetch_ci_status()` in `github.py`
- [ ] 3.9 Write integration test: mark notification as read — mock httpx `PATCH` response, verify correct URL called
- [ ] 3.10 Implement `mark_as_read()` in `github.py`
- [ ] 3.11 Write integration test: rate limit handling — mock responses with `X-RateLimit-Remaining: 50` (warning) and HTTP 403 rate limit exceeded (graceful stop)
- [ ] 3.12 Implement rate limit checking in the httpx client (check headers after each response)
- [ ] 3.13 Run `ruff format`, `ruff check`, `mypy --strict` — fix any issues

## 4. Priority engine

- [ ] 4.1 Write integration test: insert a set of notifications with different reasons and CI statuses into a real SQLite DB, compute priorities, verify ordering: review_requested+CI_pass > review_requested+CI_fail > mention > own_PR+CI_fail > team_mention > subscribed
- [ ] 4.2 Implement `compute_priority()` in `priority.py` returning `(score, tier)` tuple
- [ ] 4.3 Write integration test: recency tiebreaker — two notifications with same reason but different `updated_at`, verify more recent sorts first
- [ ] 4.4 Write integration test: edge cases — missing CI status, unknown reason type, issue (not PR) notifications
- [ ] 4.5 Implement edge case handling in `compute_priority()`
- [ ] 4.6 Write snapshot test: `forge-triage ls` output with a fixture set spanning all priority tiers — capture and verify ordering
- [ ] 4.7 Run `ruff format`, `ruff check`, `mypy --strict` — fix any issues

## 5. Sync orchestration

- [ ] 5.1 Write integration test: full initial sync — mock GitHub API (notifications + CI status + comments for top 20), run sync, verify DB contains all notifications with correct priorities and comments pre-loaded for top 20
- [ ] 5.2 Implement `sync()` in `sync.py` orchestrating: auth → fetch notifications → upsert → fetch CI → compute priority → pre-load comments → update sync metadata
- [ ] 5.3 Write integration test: incremental sync — populate DB, mock API returning only new/updated notifications, verify only changed rows updated and `last_sync_at` advanced
- [ ] 5.4 Implement incremental sync logic (pass `since` to API, skip unchanged comments)
- [ ] 5.5 Write integration test: sync with concurrent comment pre-loading — verify comments fetched for top N notifications in parallel (bounded concurrency of 5)
- [ ] 5.6 Implement concurrent comment pre-loading with `asyncio.Semaphore(5)`
- [ ] 5.7 Write snapshot test: sync summary output ("Synced: 15 new, 3 updated, 147 total")
- [ ] 5.8 Run `ruff format`, `ruff check`, `mypy --strict` — fix any issues

## 6. CLI commands

- [ ] 6.1 Write integration test: `forge-triage sync` CLI invocation — verify it calls the sync engine and prints summary
- [ ] 6.2 Implement argparse subcommand `sync` in `cli.py` with `-v` flag
- [ ] 6.3 Write snapshot test: `forge-triage ls` — table output with pre-populated DB, verify priority indicators, repo, title, reason columns
- [ ] 6.4 Write snapshot test: `forge-triage ls --json` — JSON array output
- [ ] 6.5 Implement argparse subcommand `ls` in `cli.py`
- [ ] 6.6 Write snapshot test: `forge-triage stats` output — total count, per-tier, per-repo, per-reason breakdown
- [ ] 6.7 Implement argparse subcommand `stats` in `cli.py`
- [ ] 6.8 Write snapshot test: `forge-triage sql "SELECT ..."` — table output for a query
- [ ] 6.9 Write snapshot test: `forge-triage sql --json "SELECT ..."` — JSON output
- [ ] 6.10 Write integration test: `forge-triage sql "DROP TABLE notifications"` — verify blocked without `--write`
- [ ] 6.11 Implement argparse subcommand `sql` in `cli.py` with `--json` and `--write` flags
- [ ] 6.12 Write integration test: `forge-triage done NixOS/nixpkgs#12345` — verify notification removed from DB and GitHub API mock called
- [ ] 6.13 Write integration test: `forge-triage done --reason subscribed` — verify all matching notifications removed
- [ ] 6.14 Implement argparse subcommand `done` in `cli.py`
- [ ] 6.15 Implement default action (no subcommand) → launch TUI
- [ ] 6.16 Write snapshot test: `forge-triage ls` with empty DB — verify "inbox is empty" message
- [ ] 6.17 Run `ruff format`, `ruff check`, `mypy --strict` — fix any issues

## 7. Message types and backend worker

- [ ] 7.1 Write integration test: define request/response message types — verify `MarkDoneRequest`, `FetchCommentsRequest`, `PreLoadCommentsRequest` are dataclasses with correct fields
- [ ] 7.2 Implement `messages.py` — request types (`MarkDoneRequest`, `FetchCommentsRequest`, `PreLoadCommentsRequest`) and response types (`MarkDoneResult`, `FetchCommentsResult`, `PreLoadComplete`, `ErrorResult`)
- [ ] 7.3 Write integration test: backend worker processes `MarkDoneRequest` — post request to queue, verify GitHub API mock called, DB updated, `MarkDoneResult` posted to response queue
- [ ] 7.4 Write integration test: backend worker processes `FetchCommentsRequest` — post request, verify comments fetched from API mock, stored in DB, `FetchCommentsResult` posted back
- [ ] 7.5 Write integration test: backend worker handles API failure — post request, mock API error, verify `ErrorResult` posted with error message, DB unchanged
- [ ] 7.6 Implement `backend.py` — asyncio task that reads from request queue, dispatches to `github.py`/`db.py`, posts results to response queue
- [ ] 7.7 Run `ruff format`, `ruff check`, `mypy --strict` — fix any issues

## 8. TUI — core layout and navigation

- [ ] 8.1 Write snapshot test: TUI launches with split-pane layout (notification list + detail pane), pre-populated DB with 5 notifications
- [ ] 8.2 Implement `tui/app.py` with Textual `App`, vertical split layout, `NotificationList` and `DetailPane` widgets, backend worker startup, response queue polling
- [ ] 8.3 Implement `tui/notification_list.py` — `DataTable` or `ListView` displaying priority indicator, repo, title, reason
- [ ] 8.4 Implement `tui/detail_pane.py` — renders notification title, metadata, description, and chronological comments from local DB
- [ ] 8.5 Write integration test: pressing `j`/`k` moves cursor, detail pane updates to show selected notification's content (purely local, no network)
- [ ] 8.6 Implement reactive binding: list cursor change → update detail pane from DB
- [ ] 8.7 Write snapshot test: empty inbox state — shows "inbox is empty" message
- [ ] 8.8 Write integration test: pressing `q` exits the TUI
- [ ] 8.9 Run `ruff format`, `ruff check`, `mypy --strict` — fix any issues

## 9. TUI — triage actions

- [ ] 9.1 Write integration test: pressing `d` — verify notification optimistically removed from list, `MarkDoneRequest` posted to request queue
- [ ] 9.2 Write integration test: `MarkDoneResult` with success — verify notification deleted from DB
- [ ] 9.3 Write integration test: `MarkDoneResult` with error — verify notification rolled back into list, error message displayed
- [ ] 9.4 Implement `d` keybind: optimistic removal from list → post `MarkDoneRequest` → handle `MarkDoneResult` (confirm or rollback)
- [ ] 9.5 Write integration test: pressing `o` — verify `webbrowser.open` called with correct URL (mock webbrowser)
- [ ] 9.6 Implement `o` keybind: open `html_url` in browser (direct call, no queue needed)
- [ ] 9.7 Run `ruff format`, `ruff check`, `mypy --strict` — fix any issues

## 10. TUI — filtering and grouping

- [ ] 10.1 Write integration test: press `/`, type filter text, verify list shows only matching notifications (purely local DB query, no network)
- [ ] 10.2 Implement `/` keybind: show input bar, filter list by title/repo/author match
- [ ] 10.3 Write integration test: press `Escape` clears filter, all notifications shown again
- [ ] 10.4 Write integration test: press `r`, select a reason, verify list filtered to that reason
- [ ] 10.5 Implement `r` keybind: show reason picker, filter list
- [ ] 10.6 Write snapshot test: grouped-by-repo view with collapsible headers
- [ ] 10.7 Write integration test: press `g` toggles between flat and grouped view, press `Enter` on header collapses/expands
- [ ] 10.8 Implement `g` keybind: toggle grouping, collapsible repo headers
- [ ] 10.9 Run `ruff format`, `ruff check`, `mypy --strict` — fix any issues

## 11. TUI — bulk selection

- [ ] 11.1 Write snapshot test: selected notifications have visual selection indicator
- [ ] 11.2 Write integration test: press `x` toggles selection on current notification
- [ ] 11.3 Implement `x` keybind: toggle selection state, visual indicator
- [ ] 11.4 Write integration test: press `*` selects all visible (filtered) notifications
- [ ] 11.5 Implement `*` keybind: select all visible
- [ ] 11.6 Write integration test: press `D` with selections — verify `MarkDoneRequest` posted for all selected, optimistic removal from list
- [ ] 11.7 Implement `D` keybind: bulk done via `MarkDoneRequest` for selected notifications
- [ ] 11.8 Run `ruff format`, `ruff check`, `mypy --strict` — fix any issues

## 12. TUI — lazy-load comments and new comment highlighting

- [ ] 12.1 Write integration test: navigate to notification without cached comments — verify `FetchCommentsRequest` posted, loading indicator shown, `FetchCommentsResult` handled and comments displayed
- [ ] 12.2 Implement lazy-load in detail pane: check `comments_loaded` flag → post `FetchCommentsRequest` → show loading indicator → handle `FetchCommentsResult` → display
- [ ] 12.3 Write snapshot test: notification with cached comments — no loading indicator, comments displayed immediately from DB
- [ ] 12.4 Write snapshot test: new comments highlighted — comments with `created_at` after `last_viewed_at` shown in distinct style
- [ ] 12.5 Implement new-comment highlighting: compare `created_at` vs `last_viewed_at`, apply distinct style, update `last_viewed_at` on view
- [ ] 12.6 Run `ruff format`, `ruff check`, `mypy --strict` — fix any issues

## 13. TUI — background pre-load after triage

- [ ] 13.1 Write integration test: mark 3 notifications done, verify `PreLoadCommentsRequest` posted, backend fetches comments for new top-priority notifications with `comments_loaded = 0`, `PreLoadComplete` handled
- [ ] 13.2 Implement background pre-load: after `MarkDoneResult` success, post `PreLoadCommentsRequest` → backend fetches in background → posts `PreLoadComplete` → TUI refreshes detail pane if viewing one of them
- [ ] 13.3 Write integration test: verify UI remains responsive while pre-load is in progress — user can navigate and triage
- [ ] 13.4 Run `ruff format`, `ruff check`, `mypy --strict` — fix any issues

## 14. TUI — help overlay

- [ ] 14.1 Write snapshot test: help overlay showing all keybindings
- [ ] 14.2 Implement `tui/help_screen.py` — modal screen listing all keybindings
- [ ] 14.3 Write integration test: press `?` shows help, press `?` or `Escape` dismisses
- [ ] 14.4 Implement `?` keybind: push/pop help screen
- [ ] 14.5 Run `ruff format`, `ruff check`, `mypy --strict` — fix any issues

## 15. Final integration and polish

- [ ] 15.1 Write integration test: full workflow — sync → launch TUI → navigate → filter → bulk select → done → verify request/response messages, DB state, and API calls
- [ ] 15.2 Verify all snapshot tests pass and update any that need refreshing
- [ ] 15.3 Run full test suite, `ruff format`, `ruff check`, `mypy --strict`
- [ ] 15.4 Verify `nix build` produces working binary with all features
- [ ] 15.5 Test on real GitHub account: `forge-triage sync` → `forge-triage` TUI → triage notifications → verify marked read on GitHub
