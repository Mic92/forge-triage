## Context

GitHub's notification UI is too slow for users processing 100+ notifications per session. There is no existing local-first tool that combines fast triage with full conversation context. We are building `forge-triage` — a Python CLI + Textual TUI backed by a local SQLite cache, with GitHub API as the single source of truth.

This is a greenfield project. No existing code, no migration needed.

## Goals / Non-Goals

**Goals:**
- Fast triage of 100+ GitHub notifications via a keyboard-driven TUI
- Full comment thread reading without opening a browser
- Priority-sorted inbox so the most urgent items surface first
- CLI + SQL interface for script and LLM-driven triage
- Bidirectional sync: local triage marks notifications as read on GitHub
- Works independently on multiple machines (GitHub is the sync bus)

**Non-Goals:**
- Gitea/Forgejo support (future extension, not v1)
- Posting comments, submitting reviews, or merging PRs from the tool
- Real-time / push-based notification updates (manual sync only)
- Custom notification queries beyond what GitHub's notification API provides
- Mobile or web interface

## Decisions

### 1. Project structure: single Python package with CLI entry point

```
forge-triage/
├── flake.nix
├── pyproject.toml
├── src/
│   └── forge_triage/
│       ├── __init__.py
│       ├── __main__.py          # entry point
│       ├── cli.py               # argparse CLI definitions
│       ├── db.py                # SQLite schema, queries, migrations
│       ├── github.py            # GitHub API client
│       ├── priority.py          # priority scoring engine
│       ├── sync.py              # sync orchestration
│       ├── messages.py          # request/response message types
│       ├── backend.py           # backend worker (processes request queue)
│       └── tui/
│           ├── __init__.py
│           ├── app.py           # Textual App (posts requests, handles responses)
│           ├── notification_list.py  # list widget
│           ├── detail_pane.py   # detail/comment widget
│           └── help_screen.py   # help overlay
└── tests/
    ├── conftest.py              # shared fixtures (test DB, mock API responses)
    ├── test_db.py
    ├── test_github.py
    ├── test_priority.py
    ├── test_sync.py
    ├── test_cli.py
    ├── test_messages.py
    ├── test_backend.py
    └── test_tui.py
```

**Rationale:** Flat module structure keeps imports simple. The `tui/` subpackage isolates Textual-specific code. One-to-one mapping between source modules and test modules makes test discovery obvious.

**Alternatives considered:**
- Monorepo with separate packages for core/tui/cli — rejected, unnecessary for this scope
- Single `app.py` file — rejected, would become unwieldy quickly

### 2. SQLite schema

```sql
CREATE TABLE notifications (
    notification_id   TEXT PRIMARY KEY,   -- GitHub thread ID
    repo_owner        TEXT NOT NULL,
    repo_name         TEXT NOT NULL,
    subject_type      TEXT NOT NULL,      -- 'PullRequest', 'Issue', 'Release', etc.
    subject_title     TEXT NOT NULL,
    subject_url       TEXT NOT NULL,      -- API URL
    html_url          TEXT,               -- browser URL
    reason            TEXT NOT NULL,      -- 'review_requested', 'mention', etc.
    updated_at        TEXT NOT NULL,      -- ISO 8601
    unread            INTEGER NOT NULL DEFAULT 1,
    priority_score    INTEGER NOT NULL DEFAULT 0,
    priority_tier     TEXT NOT NULL DEFAULT 'fyi',  -- 'blocking', 'action', 'fyi'
    raw_json          TEXT NOT NULL,      -- full API response for future use
    comments_loaded   INTEGER NOT NULL DEFAULT 0,
    last_viewed_at    TEXT               -- tracks "new comments" highlighting
);

CREATE TABLE comments (
    comment_id        TEXT PRIMARY KEY,
    notification_id   TEXT NOT NULL REFERENCES notifications(notification_id) ON DELETE CASCADE,
    author            TEXT NOT NULL,
    body              TEXT NOT NULL,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);

CREATE TABLE sync_metadata (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
-- Stores: 'last_sync_at', 'last_modified_header'

CREATE INDEX idx_notifications_priority ON notifications(priority_score DESC);
CREATE INDEX idx_notifications_repo ON notifications(repo_owner, repo_name);
CREATE INDEX idx_comments_notification ON comments(notification_id, created_at);
```

**Rationale:** Denormalized for read performance — the TUI queries this constantly. `raw_json` preserves the full API payload so we can extract additional fields later without re-syncing. `comments_loaded` flag avoids redundant API calls — it is reset to 0 during sync when a notification's `updated_at` changes, triggering a lazy re-fetch on next preview. `last_viewed_at` enables the "new comments" highlighting feature.

**Alternatives considered:**
- Normalized repo table — rejected, adds joins for no benefit at this scale
- JSON storage (no schema) — rejected, loses queryability which is a core feature

### 3. GitHub API client: httpx with async support

Use `httpx.AsyncClient` for GitHub API calls. Async enables concurrent comment fetching during pre-load (fetch comments for 20 notifications in parallel rather than sequentially).

**Rationale:** Pre-loading comments for 20 notifications sequentially at ~200ms/request = 4 seconds. With 5 concurrent requests = ~800ms. httpx has excellent async support and type stubs for mypy.

**Alternatives considered:**
- `requests` (sync only) — rejected, too slow for parallel comment pre-loading
- `aiohttp` — rejected, httpx has a cleaner API and better type annotations
- `gh api` subprocess — rejected, subprocess overhead per call, harder to handle pagination

### 4. Priority scoring algorithm

```python
def compute_priority(notification: dict, ci_status: str | None, is_own_pr: bool) -> tuple[int, str]:
    reason = notification["reason"]
    
    if reason == "review_requested" and ci_status == "success":
        return (1000, "blocking")  # You're blocking someone, CI is green
    if reason == "review_requested":
        return (800, "blocking")   # Review requested but CI not green
    if reason in ("mention", "assign"):
        return (600, "action")
    if is_own_pr and ci_status == "failure":
        return (500, "action")     # Your PR's CI is broken
    if reason == "team_mention":
        return (200, "fyi")
    # subscribed, comment, state_change, etc.
    return (100, "fyi")
```

Within each tier, sort by `updated_at` descending (most recent first). The score values have gaps to allow future insertion of new tiers.

**Rationale:** Simple, deterministic, fast (no API calls needed at scoring time — CI status fetched during sync). Gaps in scores allow adding sub-tiers without reshuffling.

**Alternatives considered:**
- Machine learning ranking — rejected, overkill, not enough training data
- User-configurable weights — deferred to v2, start with sensible defaults

### 5. CI status: fetch from commit status API during sync

When syncing a PR notification, fetch the combined commit status for the PR's head SHA via `GET /repos/{owner}/{repo}/commits/{sha}/status`. Store the result in `raw_json`. This is needed for priority scoring.

**Rationale:** The notifications API doesn't include CI status. One extra API call per PR notification, but results are cached and only re-fetched when `updated_at` changes.

**Alternatives considered:**
- Check runs API instead of commit status — need both actually, will use combined status endpoint which covers both
- Skip CI status entirely — rejected, it's critical for priority scoring (review-requested + CI-green is the highest urgency signal)

### 6. TUI architecture: Textual with message queue for network decoupling

The TUI never calls the GitHub API directly. All network I/O and database writes go through an event/message queue that decouples the UI from network operations. The TUI reads from SQLite directly for display (navigation, filtering, grouping) — these are fast local reads that don't need the queue.

**Architecture:**

```
┌─────────────┐     Request      ┌──────────────┐     API/DB     ┌───────────┐
│   Textual   │ ──────────────▶  │   Backend    │ ─────────────▶ │  GitHub   │
│   App/TUI   │                  │   Worker     │                │  API /    │
│             │ ◀──────────────  │  (asyncio    │ ◀───────────── │  SQLite   │
│  (widgets)  │     Response     │   task)      │                │           │
└─────────────┘                  └──────────────┘                └───────────┘
```

- **Request queue** (`asyncio.Queue`): TUI posts command messages:
  - `MarkDoneRequest(notification_ids: list[str])`
  - `FetchCommentsRequest(notification_id: str)`
  - `PreLoadCommentsRequest(top_n: int)`
- **Response queue** (`asyncio.Queue`): Backend worker posts results back:
  - `MarkDoneResult(notification_ids: list[str], errors: list[str])`
  - `FetchCommentsResult(notification_id: str, comments: list[Comment])`
  - `PreLoadComplete(loaded_ids: list[str])`
  - `ErrorResult(request: Request, error: str)`
- **Backend worker**: An asyncio task that reads from the request queue, executes GitHub API / DB operations, and posts results to the response queue.
- **TUI poll loop**: Textual's `set_interval()` or a background `Worker` that drains the response queue and updates widget state.

**Widgets:**
- **NotificationList** — a `DataTable` or custom `ListView` showing notification rows
- **DetailPane** — a `RichLog` or `Markdown` widget showing the selected notification's full content
- **HelpScreen** — a modal `Screen` overlay

**Data flow:**
1. App starts → spawns backend worker task → loads notifications from SQLite on startup (sorted by priority)
2. User navigates → `DetailPane` updates from local DB (no network)
3. User presses `d` → TUI posts `MarkDoneRequest` → shows optimistic removal from list → backend calls GitHub API + deletes from DB → posts `MarkDoneResult` → TUI confirms or rolls back on error
4. User navigates to notification with `comments_loaded = 0` → TUI posts `FetchCommentsRequest` → shows loading indicator → backend fetches + caches → posts `FetchCommentsResult` → detail pane updates
5. After done action, TUI posts `PreLoadCommentsRequest` → backend fetches comments for new top-N in background → posts `PreLoadComplete` → no visible UI change unless user is viewing one of them
6. Filters/grouping are purely local (query SQLite), no network needed

**Benefits:**
- TUI is fully testable without any network mocking — inject a fake backend that posts canned responses
- Network errors never freeze the UI — the response just includes an error
- Optimistic UI updates (remove on `d` immediately, rollback if API fails)
- Backend worker can batch/debounce requests (e.g., multiple rapid `d` presses → single bulk API call)

**Rationale:** Message queue gives complete decoupling. The TUI module has zero imports from `github.py`. Testing the TUI only requires feeding messages into the response queue. Testing the backend only requires feeding messages into the request queue.

**Alternatives considered:**
- Service layer with direct async calls — rejected, still couples TUI to service interface and needs Textual Workers for non-blocking
- Callback/protocol injection — rejected, still requires mocking in tests rather than simple message assertions
- `prompt_toolkit` — rejected, no built-in widget library for split panes
- `curses` directly — rejected, too much boilerplate for layout management

### 7. Authentication: subprocess call to `gh auth token`

```python
import subprocess

def get_github_token() -> str:
    result = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
    if result.returncode != 0 or not result.stdout.strip():
        raise AuthError("gh CLI not authenticated. Run: gh auth login")
    return result.stdout.strip()
```

**Rationale:** Zero config for users who already have `gh` set up (which is most GitHub power users). No token management, no config files, no secrets in env vars.

**Alternatives considered:**
- `GITHUB_TOKEN` env var — rejected for v1, can add as fallback later
- OAuth device flow — rejected, too complex for a CLI tool
- Keyring integration — rejected, `gh` already handles this

### 8. Sync orchestration

The `forge-triage sync` command executes these steps:

1. Get auth token via `gh auth token`
2. Fetch notifications from `GET /notifications` with `since` parameter (from `sync_metadata`)
3. For each notification:
   a. Upsert into `notifications` table
   b. Resolve `html_url` from the subject URL (API URL → browser URL)
   c. Fetch CI status for PR notifications (if not cached or updated)
   d. Compute priority score
4. Pre-load comments for top 20 by priority (concurrent, 5 at a time)
5. Detect locally-deleted notifications (present in last sync but now marked done) — mark as read on GitHub
6. Update `sync_metadata` with new timestamp
7. Print summary

Step 5 is handled by the TUI's backend worker (via `MarkDoneRequest`) and the CLI's `done` subcommand writing back immediately, so sync itself only needs to handle the fetch direction.

### 9. CLI framework: argparse

Use `argparse` from the standard library for CLI argument parsing. Entry point: `forge-triage` via `pyproject.toml` `[project.scripts]`.

```
forge-triage              → launch TUI (default command)
forge-triage sync [-v]    → fetch from GitHub
forge-triage ls [--json]  → list notifications
forge-triage stats        → summary statistics
forge-triage done <ref>   → mark as done
forge-triage sql <query>  → raw SQL query
```

**Rationale:** `argparse` is in the standard library — no extra dependency. Subcommands via `add_subparsers()` are straightforward. The default action (no subcommand) launches the TUI.

**Note:** CLI subcommands (`sync`, `done`, `ls`, `stats`, `sql`) call `github.py` and `db.py` directly — they are short-lived commands, not interactive UI, so they don't need the message queue. Only the TUI uses the request/response queue architecture for non-blocking I/O.

**Alternatives considered:**
- `click` — rejected, adds a dependency for something the stdlib handles fine
- `typer` — rejected, magic type annotation approach conflicts with mypy strict

### 10. Nix packaging

```nix
{
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  outputs = { self, nixpkgs }: {
    packages.x86_64-linux.default = /* python package built with pyproject.toml */;
    packages.aarch64-darwin.default = /* same */;
    devShells.default = /* shell with python, ruff, mypy, pytest */;
  };
}
```

Use `buildPythonApplication` with `pyproject.toml` as the build definition. All Python dependencies (textual, httpx) fetched via nixpkgs.

## Risks / Trade-offs

- **[GitHub API rate limits]** → Mitigation: incremental sync, caching, concurrent requests for pre-loading (bounded at 5). At 5000 req/hour, a full sync of 150 notifications with comments uses ~200 calls, well within limits.
- **[CI status requires extra API call per PR]** → Mitigation: cache in `raw_json`, only re-fetch when `updated_at` changes. Could skip CI fetch entirely and defer to lazy-load if rate limits are tight.
- **[Textual is a large dependency]** → Mitigation: it's well-maintained and actively developed. The alternative (curses) would require significantly more code.
- **[SQLite concurrent access]** → The backend worker is the sole writer to the database. The TUI reads from SQLite for display (local reads are fine concurrent with WAL mode). The `sync` CLI command runs separately from the TUI. WAL mode enabled for safe concurrent reads.
- **[html_url resolution requires parsing API URLs]** → Mitigation: GitHub's notification subject URL is an API URL (e.g., `api.github.com/repos/.../pulls/123`). We need to convert to `github.com/.../pull/123`. This is a simple string transformation but brittle if GitHub changes API URL format. Store both and fall back to constructing from repo+number.

## Open Questions

- Should `forge-triage` (no subcommand) auto-sync before launching the TUI, or require explicit `forge-triage sync` first? Leaning toward: show stale data immediately, offer a keybind (`S`) to sync from within the TUI (which would post a `SyncRequest` through the message queue).
- How to handle GitHub notifications for private repos the user no longer has access to? The API may return 404 when fetching details. Mitigation: store what we can from the notification payload, skip detail fetching gracefully.
- Should the SQL `--write` flag exist at all, or should the database always be treated as read-only from the SQL interface? The cache is rebuildable, so writes aren't dangerous, but they could cause confusing state.

## Testing Strategy

### What gets mocked
- **GitHub API**: All HTTP calls mocked with `pytest-httpx` or fixture JSON files recorded from real API responses. Never hit the real GitHub API in tests.
- **`gh auth token`**: Mocked via `subprocess` patching to return test tokens or simulate failures.
- **Browser opening** (`webbrowser.open`): Mocked to verify URL passed without actually opening a browser.

### What gets tested for real
- **SQLite**: Use temporary in-memory databases (`":memory:"`) or `tmp_path` file databases. Test real schema creation, queries, upserts, cascading deletes — no mocking.
- **Priority engine**: Pure functions, tested with synthetic data. No mocking needed.
- **CLI output**: Use `subprocess.run` or direct function calls to invoke CLI commands and assert stdout/stderr against expected output.
- **TUI**: Use Textual's `App.run_test()` with `pilot.press()` to simulate keystrokes and assert widget state. Inject a fake backend that posts canned response messages — no network mocking needed. Pre-populate with test database for local reads.
- **Backend worker**: Test independently by posting request messages to its input queue and asserting the response messages it produces. Mock only the GitHub API (httpx), use real SQLite.

### Test layers
1. **Snapshot tests** (primary): CLI output formatting, TUI visual layout (Textual snapshots), SQL query results
2. **Integration tests** (primary): Full sync flow with mocked HTTP, CLI commands against real SQLite, TUI interactions with pre-populated databases
3. **Unit tests** (sparingly): Only for pure algorithmic logic where integration tests would be awkward (e.g., priority score edge cases)

Prefer tests that exercise real code paths end-to-end over isolated unit tests. Use real SQLite, real CLI runners, real Textual test pilots — only mock external boundaries (GitHub API, subprocess, browser).

### TDD workflow
Every feature implementation follows:
1. Write a failing pytest test (prefer integration/snapshot) that asserts the expected behavior
2. Implement the minimal code to make the test pass
3. Refactor while keeping tests green
4. Run `ruff format`, `ruff check`, `mypy --strict` before committing
