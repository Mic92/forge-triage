## Context

The TUI currently uses a fixed two-pane layout (`NotificationList` DataTable on top, `DetailPane` Static widget on bottom) within a single `Vertical` container. The `DetailPane` is a flat `Static` widget that renders title, metadata, and comments as markup text. All keybindings are global on `TriageApp`. The backend uses an async request/response queue pattern (`messages.py`, `backend.py`) for GitHub API calls. The GitHub API client (`github.py`) currently handles notifications (REST), comments (REST), and subject details (GraphQL), but has no support for PR reviews, review comments, or diffs.

Textual ≥0.89 provides `TabbedContent`/`TabPane` for tabbed layouts, `Screen.push`/`Screen.pop` for screen stacking, and built-in syntax highlighting via Rich. The app uses Rich markup throughout.

## Goals / Non-Goals

**Goals:**
- Full-screen detail view as a pushed Textual `Screen` for both PRs and issues
- Tabbed PR view (Description / Conversations / Files Changed) using Textual `TabbedContent`
- Resizable split pane with draggable divider in the main list view
- Context-aware keybindings (`q`, `Escape`, `r`) that behave differently per screen
- Review workflow via command palette (approve, request changes, reply, resolve)
- Syntax-highlighted inline diffs with review comments and file sidebar
- Light Markdown formatting for descriptions and comments
- Local caching of PR review data to minimize API calls

**Non-Goals:**
- Full Markdown rendering (tables, images, checkboxes) — only light formatting
- Merge/close/edit PR actions — review actions only
- Batched pending reviews — comments are submitted individually
- External editor integration for replies
- Offline-first design — the detail view requires network for initial data fetch
- Code suggestions/annotations (GitHub's "suggestion" feature)

## Decisions

### 1. Detail view as a pushed Textual Screen

**Decision**: Use `self.app.push_screen(DetailScreen(...))` to show the detail view as a full-screen overlay.

**Rationale**: Textual's screen stack is the idiomatic way to show full-screen views that replace the current content. The `DetailScreen` gets its own `BINDINGS` that naturally shadow the app-level bindings, solving the context-aware keybinding problem without complex conditional logic. `q` and `Escape` call `self.app.pop_screen()` on the detail screen, while remaining quit/clear-filter on the main screen.

**Alternatives considered**:
- *Visibility toggling*: Hide/show containers within the same screen. Fragile, leaks focus, doesn't isolate keybindings.
- *Replace the compose tree*: Remove and re-mount widgets dynamically. Slow and error-prone with Textual's DOM lifecycle.

### 2. Resizable split via a custom Splitter widget

**Decision**: Replace the fixed `Vertical` container with a custom `SplitContainer` that renders a draggable divider bar between the notification list and the preview pane. The divider responds to mouse drag events to resize.

**Rationale**: Textual doesn't ship a built-in resizable split pane widget. A custom widget wrapping two children with a `Static` divider bar is straightforward — capture `MouseDown`/`MouseMove` on the divider, compute new height ratios, and apply CSS `height` updates. This is a well-trodden pattern in the Textual community.

**Alternatives considered**:
- *Fixed ratio with keyboard toggle*: Simpler but less flexible. Users want fluid resizing.
- *Third-party Textual splitter*: No well-maintained library exists for this.

### 3. Context-aware keybindings via Screen-level BINDINGS

**Decision**: Each screen defines its own `BINDINGS`. The main `TriageApp` keeps its current bindings. `DetailScreen` defines `q` → `pop_screen`, `Escape` → `pop_screen`, `r` → `refresh_detail`, overriding the app-level meanings.

**Rationale**: Textual's binding resolution walks from the focused widget up to the screen, then to the app. Screen-level bindings take precedence over app-level bindings for the same key. This is the intended mechanism — no hacks needed.

**Impact**: The `?` help screen must become context-aware too, showing different keybindings depending on which screen is active. The `HelpScreen` should read bindings from the active screen.

### 4. PR detail data model: new DB tables for reviews and diffs

**Decision**: Add three new tables: `pr_reviews`, `review_comments`, and `pr_files`. Cache PR metadata (author, description, labels) in a new `pr_details` table. Introduce a `pr_data_loaded` flag on the notifications table.

```
pr_details:
  notification_id (FK), pr_number, author, body, labels_json, base_ref, head_ref, loaded_at

pr_reviews:
  review_id (PK), notification_id (FK), author, state, body, submitted_at

review_comments:
  comment_id (PK), review_id (FK), notification_id (FK), author, body, path, diff_hunk,
  line, side, in_reply_to_id, is_resolved, created_at, updated_at

pr_files:
  file_id (PK), notification_id (FK), filename, status, additions, deletions, patch
```

**Rationale**: The current `comments` table only stores issue-style comments (flat). PR reviews are a different structure: reviews contain review comments, which are threaded and anchored to specific code lines. Separate tables reflect GitHub's data model and avoid conflating two different things. Caching locally avoids repeated API calls when switching tabs.

**Alternatives considered**:
- *No caching, always fetch*: Too slow — switching tabs would block on network. The current app already caches comments.
- *Single `pr_data` JSON blob*: Loses queryability (e.g., can't query resolved threads). Harder to update incrementally.

### 5. GitHub API: GraphQL for reviews, REST for diffs

**Decision**: Fetch PR reviews and review comments via GraphQL (to get threaded structure, `isResolved`, and inline code context in one query). Fetch file diffs via REST (`GET /repos/{owner}/{repo}/pulls/{number}/files`) since the REST response includes parsed patch hunks ready to render.

**Rationale**: The GraphQL `pullRequest.reviews` and `reviewThreads` APIs provide threaded conversation structure with resolution state, which isn't available via REST. File diffs are simpler via REST — the response includes `patch` text per file, which is what we need for rendering.

**Alternatives considered**:
- *All GraphQL*: The diff/patch data in GraphQL is nested and paginated differently. REST is simpler for file listings.
- *All REST*: Review threads and resolution state require multiple REST calls and client-side assembly. GraphQL gives us the tree in one query.

### 6. Tabbed content with lazy loading

**Decision**: Use Textual's `TabbedContent` with three `TabPane`s. Each tab loads its data lazily on first activation. The Description tab loads immediately (data comes with the initial PR details fetch). Conversations and Files Changed tabs fetch on first switch.

**Rationale**: Lazy loading avoids fetching review threads and diffs upfront if the user only wants to see the description. The `r` refresh key reloads all tabs' data (invalidating the loaded flag), but only re-renders the active tab.

### 7. Review actions via command palette

**Decision**: A keybinding (`:` or `Ctrl+p`) opens a filterable command palette listing available review actions. Actions depend on context: on a conversation thread, "Reply" and "Resolve" are available; globally, "Approve" and "Request Changes" are available.

**Rationale**: A command palette scales better than dedicated keybindings for each action — it's discoverable (shows available actions), doesn't consume limited key space, and matches a UI pattern users know from VS Code and GitHub.

**Implementation**: Use Textual's built-in `CommandPalette` or a simple `OptionList` in a modal `Screen`. Actions post request messages to the backend queue, same as existing `MarkDoneRequest` etc.

### 8. Inline reply editor

**Decision**: Use a Textual `TextArea` widget that appears inline below the comment being replied to. Submit with `Ctrl+Enter`, cancel with `Escape`.

**Rationale**: `TextArea` is a built-in Textual widget with multi-line editing, cursor movement, and scroll. It's sufficient for short review replies. The inline placement keeps context visible.

### 9. Diff rendering with syntax highlighting

**Decision**: Parse the `patch` field from GitHub's file diff response and render each hunk using Rich's `Syntax` class for language-aware highlighting, plus diff coloring (green/red backgrounds for added/removed lines). Review comments are interpolated at the correct line positions within the diff.

**Rationale**: Rich's `Syntax` handles language detection from filename extension and provides terminal-quality highlighting. Overlaying diff coloring (background) on syntax highlighting (foreground) gives the best readability.

**File sidebar**: A `ListView` in the left portion of the Files Changed tab pane, showing filenames with add/delete counts. Selecting a file scrolls the diff pane to that file's section. Collapsible via a keybinding (`b` for sidebar toggle).

### 10. Light Markdown formatting

**Decision**: Implement a simple markup pass that converts:
- `# headings` → `[bold]headings[/bold]`
- `` `inline code` `` → styled spans
- ```` ```code blocks``` ```` → Rich `Syntax` rendering
- `**bold**` / `*italic*` → Rich markup equivalents
- URLs → clickable (Textual supports link actions)

Everything else rendered as plain text.

**Rationale**: Textual's full `Markdown` widget is heavyweight and has rendering quirks. A lightweight pass using Rich markup gives 80% of the value (code blocks and headers are most important) without the complexity.

### 11. New message types for review operations

**Decision**: Extend `messages.py` with new request/response types:

- `FetchPRDetailRequest` / `FetchPRDetailResult` — fetch PR metadata, reviews, review comments, files
- `PostReviewCommentRequest` / `PostReviewCommentResult` — post a reply to a review thread
- `SubmitReviewRequest` / `SubmitReviewResult` — approve or request changes
- `ResolveThreadRequest` / `ResolveThreadResult` — resolve/unresolve a review thread

**Rationale**: Follows the established async queue pattern. The backend worker dispatches to the appropriate GitHub API handler. The TUI remains non-blocking.

### 12. Module structure

New modules:
```
src/forge_triage/tui/
├── detail_screen.py      # DetailScreen (pushed Screen), tab orchestration
├── tabs/
│   ├── description.py    # Description tab content
│   ├── conversations.py  # Threaded review conversations
│   └── files_changed.py  # Diff view with file sidebar
├── widgets/
│   ├── split_container.py  # Resizable split pane
│   ├── command_palette.py  # Review action palette
│   ├── diff_view.py        # Diff rendering widget
│   ├── markdown_light.py   # Light Markdown formatter
│   └── reply_editor.py     # Inline TextArea for replies

src/forge_triage/
├── github_pr.py          # PR-specific GitHub API (reviews, diffs, mutations)
├── pr_db.py              # PR detail DB operations (new tables)
```

**Rationale**: Keeps the existing modules untouched where possible. New functionality lives in new files. The `tui/tabs/` and `tui/widgets/` subdirectories prevent the `tui/` directory from becoming a flat dump of files.

## Risks / Trade-offs

**[Large scope]** → This is a substantial change touching many parts of the app. Mitigate by implementing incrementally: resizable split first, then detail screen skeleton, then tabs one by one. Each step is independently testable and useful.

**[GraphQL query complexity]** → PR review threads with deeply nested replies could hit GraphQL node limits. → Mitigate with pagination (cursor-based) and conservative `first:` limits (50 review threads per query).

**[Diff rendering performance]** → Large PRs (hundreds of files, thousands of lines) may render slowly. → Mitigate with virtual scrolling (only render visible hunks) and lazy hunk parsing. Consider a file-at-a-time rendering strategy.

**[Textual TabbedContent limitations]** → TabbedContent may have focus/scroll issues with complex nested widgets. → Mitigate by testing early with realistic content. Fall back to custom tab implementation if needed.

**[Breaking keybinding change]** → Context-aware `q` may surprise users who expect it to always quit. → Mitigate with clear status bar indicators showing "Back" vs "Quit" depending on context. Update help screen.

**[Review action error handling]** → Posting reviews can fail (permissions, conflicts, deleted PRs). → All mutations go through the backend queue with `ErrorResult` handling, same as existing mark-done. Show user-visible error notifications.

**[Rate limiting on review mutations]** → Individual comment submission means more API calls than batched reviews. → Acceptable for typical review volumes (< 20 comments per PR). If it becomes an issue, batching can be added later as an optimization.

## Testing Strategy

**Unit tests (no network, no TUI)**:
- `pr_db.py`: Test all CRUD operations on new tables with a real in-memory SQLite database. Test schema migrations.
- `github_pr.py`: Test GraphQL query construction and response parsing with canned JSON fixtures. Test diff patch parsing.
- `markdown_light.py`: Test Markdown → Rich markup conversion with various inputs.
- `diff_view.py`: Test diff hunk parsing, line numbering, and review comment interpolation with sample patches.

**Integration tests (real SQLite, mocked HTTP)**:
- `backend.py` extensions: Test new request/response message handling with mocked `httpx` responses. Verify DB state after fetch and mutation operations.
- End-to-end PR data flow: Fetch PR details → store in DB → read back → verify structure.

**TUI snapshot tests (Textual `App.run_test()`)**:
- `detail_screen.py`: Snapshot each tab with pre-populated DB data. Verify layout, tab switching, and keybinding behavior.
- `split_container.py`: Snapshot the resizable split at different ratios.
- `notification_list.py`: Verify `Enter` key triggers screen push.
- `command_palette.py`: Snapshot the palette with available actions.
- Context-aware keybindings: Test that `q` pops screen in detail view and quits in main view.

**Components needing mocks**:
- GitHub API (`httpx` calls in `github_pr.py`) — use `respx` or `httpx.MockTransport` with recorded responses
- `gh auth token` subprocess — mock with `monkeypatch`

**Components tested with real implementations**:
- SQLite database — use in-memory `:memory:` databases
- Textual TUI — use `App.run_test()` with pilot for key simulation
- Rich markup rendering — test actual output

## Open Questions

1. **Thread pagination**: GitHub limits review thread responses. Should we paginate eagerly (fetch all) or lazily (fetch more on scroll)? Leaning toward eager fetch with a cap (first 100 threads).

2. **Stale data in detail view**: If a PR is updated while the user is viewing it, should we show a "stale data" indicator, or rely on the user pressing `r` to refresh?

3. **Issue detail view scope**: The proposal says `Enter` works on all notifications. For issues, should the detail view just be a full-screen version of the current detail pane, or should it also support threaded comments and reply?
