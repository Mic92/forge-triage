## 1. Project scaffolding

- [x] 1.1 Create `pyproject.toml` with project metadata, entry point (`forge-triage`), and dependencies (textual, httpx)
- [x] 1.2 Create `flake.nix` with `buildPythonApplication`, devShell (python, ruff, mypy, pytest, pytest-httpx), and multi-platform support (x86_64-linux, aarch64-darwin)
- [x] 1.3 Create package skeleton: `src/forge_triage/__init__.py`, `__main__.py`, and empty modules (`cli.py`, `db.py`, `github.py`, `priority.py`, `sync.py`, `messages.py`, `backend.py`, `tui/__init__.py`, `tui/app.py`)
- [x] 1.4 Create `tests/conftest.py` with shared fixtures: temporary SQLite database, sample GitHub API notification JSON fixtures, mock `gh auth token` helper, fake backend (canned response queue for TUI tests)
- [x] 1.5 Verify `nix build` produces a working `forge-triage` binary, `nix develop` provides all dev tools, `pytest` runs (even with zero tests)
- [x] 1.6 Run `ruff format`, `ruff check`, `mypy --strict` — fix any issues

## 2. Database layer

- [x] 2.1 Write integration test: create a DB, verify schema (tables `notifications`, `comments`, `sync_metadata` exist with correct columns), insert and query a notification
- [x] 2.2 Implement `db.py`: `get_db_path()` (XDG resolution), `init_db()` (schema creation with WAL mode), connection helper
- [x] 2.3 Write integration test: XDG path resolution — test with `$XDG_DATA_HOME` set, unset (fallback to `$HOME/.local/share/forge-triage/`)
- [x] 2.4 Implement XDG path logic in `get_db_path()`
- [x] 2.5 Write integration test: upsert notification — insert new, update existing (changed `updated_at`), verify idempotency
- [x] 2.6 Write integration test: upsert with `updated_at` change resets `comments_loaded` to 0 — verify previously loaded comments are invalidated
- [x] 2.7 Implement `upsert_notification()` and `delete_notification()` in `db.py` — upsert sets `comments_loaded = 0` when `updated_at` changes
- [x] 2.8 Write integration test: comment storage — insert comments, query by notification_id ordered by created_at, verify cascade delete (delete notification → comments gone)
- [x] 2.9 Implement `upsert_comments()` and `get_comments()` in `db.py`
- [x] 2.10 Write integration test: sync metadata — store and retrieve `last_sync_at`, update it
- [x] 2.11 Implement `get_sync_meta()` and `set_sync_meta()` in `db.py`
- [x] 2.12 Run `ruff format`, `ruff check`, `mypy --strict` — fix any issues

## 3. GitHub API client

- [x] 3.1 Write integration test: `get_github_token()` — mock `subprocess.run` for success (returns token), failure (non-zero exit), and empty output
- [x] 3.2 Implement `get_github_token()` in `github.py`
- [x] 3.3 Write integration test: fetch notifications — mock httpx responses with recorded GitHub API JSON, verify parsed notification list matches expected structure, test pagination (multiple pages via `Link` header)
- [x] 3.4 Implement `fetch_notifications()` in `github.py` using `httpx.AsyncClient` with Bearer auth and `since` parameter
- [x] 3.5 Write integration test: fetch comments for a PR — mock httpx with recorded comments JSON, verify parsed comments match expected structure
- [x] 3.6 Implement `fetch_comments()` in `github.py` — resolve comment URL from notification subject, fetch and parse
- [x] 3.7 Write integration test: fetch CI status for a PR — mock httpx with combined status JSON, verify parsed status
- [x] 3.8 Implement `fetch_ci_status()` in `github.py`
- [x] 3.9 Write integration test: mark notification as read — mock httpx `PATCH` response, verify correct URL called
- [x] 3.10 Implement `mark_as_read()` in `github.py`
- [x] 3.11 Write integration test: rate limit handling — mock responses with `X-RateLimit-Remaining: 50` (warning) and HTTP 403 rate limit exceeded (graceful stop)
- [x] 3.12 Implement rate limit checking in the httpx client (check headers after each response)
- [x] 3.13 Run `ruff format`, `ruff check`, `mypy --strict` — fix any issues

## 4. Priority engine

- [x] 4.1 Write integration test: insert a set of notifications with different reasons and CI statuses into a real SQLite DB, compute priorities, verify ordering: review_requested+CI_pass > review_requested+CI_fail > mention > own_PR+CI_fail > team_mention > subscribed
- [x] 4.2 Implement `compute_priority()` in `priority.py` returning `(score, tier)` tuple
- [x] 4.3 Write integration test: recency tiebreaker — two notifications with same reason but different `updated_at`, verify more recent sorts first
- [x] 4.4 Write integration test: edge cases — missing CI status, unknown reason type, issue (not PR) notifications
- [x] 4.5 Implement edge case handling in `compute_priority()`
- [x] 4.6 Write snapshot test: `forge-triage ls` output with a fixture set spanning all priority tiers — capture and verify ordering
- [x] 4.7 Run `ruff format`, `ruff check`, `mypy --strict` — fix any issues

## 5. Sync orchestration

- [x] 5.1 Write integration test: full initial sync — mock GitHub API (notifications + CI status + comments for top 20), run sync, verify DB contains all notifications with correct priorities and comments pre-loaded for top 20
- [x] 5.2 Implement `sync()` in `sync.py` orchestrating: auth → fetch notifications → upsert → fetch CI → compute priority → pre-load comments → update sync metadata
- [x] 5.3 Write integration test: incremental sync — populate DB, mock API returning only new/updated notifications, verify only changed rows updated and `last_sync_at` advanced
- [x] 5.4 Implement incremental sync logic (pass `since` to API, skip unchanged comments)
- [x] 5.5 Write integration test: sync with concurrent comment pre-loading — verify comments fetched for top N notifications in parallel (bounded concurrency of 5)
- [x] 5.6 Implement concurrent comment pre-loading with `asyncio.Semaphore(5)`
- [x] 5.7 Write snapshot test: sync summary output ("Synced: 15 new, 3 updated, 147 total")
- [x] 5.8 Run `ruff format`, `ruff check`, `mypy --strict` — fix any issues

## 6. CLI commands

- [x] 6.1 Write integration test: `forge-triage sync` CLI invocation — verify it calls the sync engine and prints summary
- [x] 6.2 Implement argparse subcommand `sync` in `cli.py` with `-v` flag
- [x] 6.3 Write snapshot test: `forge-triage ls` — table output with pre-populated DB, verify priority indicators, repo, title, reason columns
- [x] 6.4 Write snapshot test: `forge-triage ls --json` — JSON array output
- [x] 6.5 Implement argparse subcommand `ls` in `cli.py`
- [x] 6.6 Write snapshot test: `forge-triage stats` output — total count, per-tier, per-repo, per-reason breakdown
- [x] 6.7 Implement argparse subcommand `stats` in `cli.py`
- [x] 6.8 Write snapshot test: `forge-triage sql "SELECT ..."` — table output for a query
- [x] 6.9 Write snapshot test: `forge-triage sql --json "SELECT ..."` — JSON output
- [x] 6.10 Write integration test: `forge-triage sql "DROP TABLE notifications"` — verify blocked without `--write`
- [x] 6.11 Implement argparse subcommand `sql` in `cli.py` with `--json` and `--write` flags
- [x] 6.12 Write integration test: `forge-triage done NixOS/nixpkgs#12345` — verify notification removed from DB and GitHub API mock called
- [x] 6.13 Write integration test: `forge-triage done --reason subscribed` — verify all matching notifications removed
- [x] 6.14 Implement argparse subcommand `done` in `cli.py`
- [x] 6.15 Implement default action (no subcommand) → launch TUI
- [x] 6.16 Write snapshot test: `forge-triage ls` with empty DB — verify "inbox is empty" message
- [x] 6.17 Run `ruff format`, `ruff check`, `mypy --strict` — fix any issues

## 7. Message types and backend worker

- [x] 7.1 Write integration test: define request/response message types — verify `MarkDoneRequest`, `FetchCommentsRequest`, `PreLoadCommentsRequest` are dataclasses with correct fields
- [x] 7.2 Implement `messages.py` — request types (`MarkDoneRequest`, `FetchCommentsRequest`, `PreLoadCommentsRequest`) and response types (`MarkDoneResult`, `FetchCommentsResult`, `PreLoadComplete`, `ErrorResult`)
- [x] 7.3 Write integration test: backend worker processes `MarkDoneRequest` — post request to queue, verify GitHub API mock called, DB updated, `MarkDoneResult` posted to response queue
- [x] 7.4 Write integration test: backend worker processes `FetchCommentsRequest` — post request, verify comments fetched from API mock, stored in DB, `FetchCommentsResult` posted back
- [x] 7.5 Write integration test: backend worker handles API failure — post request, mock API error, verify `ErrorResult` posted with error message, DB unchanged
- [x] 7.6 Implement `backend.py` — asyncio task that reads from request queue, dispatches to `github.py`/`db.py`, posts results to response queue
- [x] 7.7 Run `ruff format`, `ruff check`, `mypy --strict` — fix any issues

## 8. TUI — core layout and navigation

- [x] 8.1 Write snapshot test: TUI launches with split-pane layout (notification list + detail pane), pre-populated DB with 5 notifications
- [x] 8.2 Implement `tui/app.py` with Textual `App`, vertical split layout, `NotificationList` and `DetailPane` widgets, backend worker startup, response queue polling
- [x] 8.3 Implement `tui/notification_list.py` — `DataTable` or `ListView` displaying priority indicator, repo, title, reason
- [x] 8.4 Implement `tui/detail_pane.py` — renders notification title, metadata, description, and chronological comments from local DB
- [x] 8.5 Write integration test: pressing `j`/`k` moves cursor, detail pane updates to show selected notification's content (purely local, no network)
- [x] 8.6 Implement reactive binding: list cursor change → update detail pane from DB
- [x] 8.7 Write snapshot test: empty inbox state — shows "inbox is empty" message
- [x] 8.8 Write integration test: pressing `q` exits the TUI
- [x] 8.9 Run `ruff format`, `ruff check`, `mypy --strict` — fix any issues

## 9. TUI — triage actions

- [x] 9.1 Write integration test: pressing `d` — verify notification optimistically removed from list, `MarkDoneRequest` posted to request queue
- [x] 9.2 Write integration test: `MarkDoneResult` with success — verify notification deleted from DB
- [x] 9.3 Write integration test: `MarkDoneResult` with error — verify notification rolled back into list, error message displayed
- [x] 9.4 Implement `d` keybind: optimistic removal from list → post `MarkDoneRequest` → handle `MarkDoneResult` (confirm or rollback)
- [x] 9.5 Write integration test: pressing `o` — verify `webbrowser.open` called with correct URL (mock webbrowser)
- [x] 9.6 Implement `o` keybind: open `html_url` in browser (direct call, no queue needed)
- [x] 9.7 Run `ruff format`, `ruff check`, `mypy --strict` — fix any issues

## 10. TUI — filtering and grouping

- [x] 10.1 Write integration test: press `/`, type filter text, verify list shows only matching notifications (purely local DB query, no network)
- [x] 10.2 Implement `/` keybind: show input bar, filter list by title/repo/author match
- [x] 10.3 Write integration test: press `Escape` clears filter, all notifications shown again
- [x] 10.4 Write integration test: press `r`, select a reason, verify list filtered to that reason
- [x] 10.5 Implement `r` keybind: show reason picker, filter list
- [x] 10.6 Write snapshot test: grouped-by-repo view with collapsible headers
- [x] 10.7 Write integration test: press `g` toggles between flat and grouped view, press `Enter` on header collapses/expands
- [x] 10.8 Implement `g` keybind: toggle grouping, collapsible repo headers
- [x] 10.9 Run `ruff format`, `ruff check`, `mypy --strict` — fix any issues

## 11. TUI — bulk selection

- [x] 11.1 Write snapshot test: selected notifications have visual selection indicator
- [x] 11.2 Write integration test: press `x` toggles selection on current notification
- [x] 11.3 Implement `x` keybind: toggle selection state, visual indicator
- [x] 11.4 Write integration test: press `*` selects all visible (filtered) notifications
- [x] 11.5 Implement `*` keybind: select all visible
- [x] 11.6 Write integration test: press `D` with selections — verify `MarkDoneRequest` posted for all selected, optimistic removal from list
- [x] 11.7 Implement `D` keybind: bulk done via `MarkDoneRequest` for selected notifications
- [x] 11.8 Run `ruff format`, `ruff check`, `mypy --strict` — fix any issues

## 12. TUI — lazy-load comments and new comment highlighting

- [x] 12.1 Write integration test: navigate to notification without cached comments — verify `FetchCommentsRequest` posted, loading indicator shown, `FetchCommentsResult` handled and comments displayed
- [x] 12.2 Implement lazy-load in detail pane: check `comments_loaded` flag → post `FetchCommentsRequest` → show loading indicator → handle `FetchCommentsResult` → display
- [x] 12.3 Write snapshot test: notification with cached comments — no loading indicator, comments displayed immediately from DB
- [x] 12.4 Write snapshot test: new comments highlighted — comments with `created_at` after `last_viewed_at` shown in distinct style
- [x] 12.5 Implement new-comment highlighting: compare `created_at` vs `last_viewed_at`, apply distinct style, update `last_viewed_at` on view
- [x] 12.6 Run `ruff format`, `ruff check`, `mypy --strict` — fix any issues

## 13. TUI — background pre-load after triage

- [x] 13.1 Write integration test: mark 3 notifications done, verify `PreLoadCommentsRequest` posted, backend fetches comments for new top-priority notifications with `comments_loaded = 0`, `PreLoadComplete` handled
- [x] 13.2 Implement background pre-load: after `MarkDoneResult` success, post `PreLoadCommentsRequest` → backend fetches in background → posts `PreLoadComplete` → TUI refreshes detail pane if viewing one of them
- [x] 13.3 Write integration test: verify UI remains responsive while pre-load is in progress — user can navigate and triage
- [x] 13.4 Run `ruff format`, `ruff check`, `mypy --strict` — fix any issues

## 14. TUI — help overlay

- [x] 14.1 Write snapshot test: help overlay showing all keybindings
- [x] 14.2 Implement `tui/help_screen.py` — modal screen listing all keybindings
- [x] 14.3 Write integration test: press `?` shows help, press `?` or `Escape` dismisses
- [x] 14.4 Implement `?` keybind: push/pop help screen
- [x] 14.5 Run `ruff format`, `ruff check`, `mypy --strict` — fix any issues

## 15. Final integration and polish

- [x] 15.1 Write integration test: full workflow — sync → launch TUI → navigate → filter → bulk select → done → verify request/response messages, DB state, and API calls
- [x] 15.2 Verify all snapshot tests pass and update any that need refreshing
- [x] 15.3 Run full test suite, `ruff format`, `ruff check`, `mypy --strict`
- [x] 15.4 Verify `nix build` produces working binary with all features
- [ ] 15.5 Test on real GitHub account: `forge-triage sync` → `forge-triage` TUI → triage notifications → verify marked read on GitHub
