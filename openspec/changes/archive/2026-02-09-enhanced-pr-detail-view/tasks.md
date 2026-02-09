## 1. Database Schema & PR Data Layer

- [x] 1.1 Write failing tests for PR data tables (pr_details, pr_reviews, review_comments, pr_files) — test table creation, insert, query, cascade deletion from notifications
- [x] 1.2 Create `src/forge_triage/pr_db.py` with schema migration adding new tables and CRUD functions (upsert_pr_details, upsert_pr_reviews, upsert_review_comments, upsert_pr_files, get_pr_details, get_review_threads, get_pr_files, delete_pr_data)
- [x] 1.3 Write failing tests for cache invalidation — verify delete+re-insert flow on refresh
- [x] 1.4 Implement cache invalidation in `pr_db.py` (delete_pr_data_for_notification)
- [x] 1.5 Run ruff format, ruff check, mypy on `pr_db.py`

## 2. GitHub PR API Client

- [x] 2.1 Write failing tests for GraphQL query construction — review threads query with pagination cursors, single PR, multiple threads
- [x] 2.2 Implement `src/forge_triage/github_pr.py` — `build_review_threads_query()` and `parse_review_threads_response()` for fetching PR reviews and review comments via GraphQL
- [x] 2.3 Write failing tests for PR metadata fetching — parse PR author, body, labels from GraphQL response
- [x] 2.4 Implement `fetch_pr_metadata()` in `github_pr.py` — GraphQL query for PR number, author, body, labels, base/head refs
- [x] 2.5 Write failing tests for REST file diff fetching — parse filename, status, additions, deletions, patch from canned REST responses, including pagination
- [x] 2.6 Implement `fetch_pr_files()` in `github_pr.py` — REST GET `/repos/{owner}/{repo}/pulls/{number}/files` with Link-header pagination
- [x] 2.7 Write failing tests for review mutations — post reply, submit review (approve/request_changes), resolve/unresolve thread
- [x] 2.8 Implement mutation functions in `github_pr.py` — `post_review_reply()`, `submit_review()`, `resolve_review_thread()`, `unresolve_review_thread()`
- [x] 2.9 Write failing tests for GraphQL pagination — verify cursor-based fetching when threads exceed per-query limit
- [x] 2.10 Implement pagination in `fetch_review_threads()` with cursor-based iteration
- [x] 2.11 Run ruff format, ruff check, mypy on `github_pr.py`

## 3. Async Message Types & Backend Extensions

- [x] 3.1 Write failing tests for new message types — verify FetchPRDetailRequest, PostReviewCommentRequest, SubmitReviewRequest, ResolveThreadRequest round-trip through backend worker with mocked API
- [x] 3.2 Add new request/response message types to `src/forge_triage/messages.py` — FetchPRDetailRequest/Result, PostReviewCommentRequest/Result, SubmitReviewRequest/Result, ResolveThreadRequest/Result
- [x] 3.3 Implement backend handlers in `src/forge_triage/backend.py` — dispatch new request types to `github_pr.py` functions, store results in `pr_db.py`, return response messages
- [x] 3.4 Write failing tests for backend error handling — API failures return ErrorResult with descriptive messages
- [x] 3.5 Implement error handling in backend handlers for new request types
- [x] 3.6 Run ruff format, ruff check, mypy on `messages.py` and `backend.py`

## 4. Light Markdown Formatter

- [x] 4.1 Write failing tests for Markdown-to-Rich-markup conversion — headings, bold, italic, inline code, fenced code blocks, URLs, plain text passthrough
- [x] 4.2 Implement `src/forge_triage/tui/widgets/markdown_light.py` — `render_markdown(text: str) -> str` converting Markdown to Rich markup with syntax highlighting for fenced code blocks
- [x] 4.3 Write failing edge case tests — nested formatting, empty input, malformed Markdown, code blocks with language hints
- [x] 4.4 Handle edge cases in `markdown_light.py`
- [x] 4.5 Run ruff format, ruff check, mypy on `markdown_light.py`

## 5. Resizable Split Pane Widget

- [x] 5.1 Write failing TUI snapshot tests for `SplitContainer` — default ratio, custom ratio, minimum pane heights
- [x] 5.2 Implement `src/forge_triage/tui/widgets/split_container.py` — custom widget with draggable divider bar, mouse event handling for resize, CSS height updates
- [x] 5.3 Write failing TUI integration tests — verify mouse drag changes pane sizes, minimum height is enforced
- [x] 5.4 Implement mouse drag handling in `SplitContainer` (MouseDown/MouseMove/MouseUp on divider)
- [x] 5.5 Replace `Vertical(id="main-container")` in `app.py` with `SplitContainer` wrapping `NotificationList` and `DetailPane`
- [x] 5.6 Run ruff format, ruff check, mypy on `split_container.py` and `app.py`

## 6. Preview Pane Updates

- [x] 6.1 Write failing tests for updated preview pane — verify it shows author, description (with light Markdown), and labels; verify CI status is NOT shown
- [x] 6.2 Update `src/forge_triage/tui/detail_pane.py` — show author, description body (rendered via `markdown_light`), and labels. Remove CI status display from preview.
- [x] 6.3 Write failing tests for preview pane with missing data — no labels, no description, no author
- [x] 6.4 Handle missing data gracefully in `detail_pane.py`
- [x] 6.5 Run ruff format, ruff check, mypy on `detail_pane.py`

## 7. Detail Screen Skeleton & Navigation

- [x] 7.1 Write failing TUI integration tests — `Enter` on notification pushes DetailScreen, `q` pops it, `Escape` pops it, list state is preserved after return
- [x] 7.2 Implement `src/forge_triage/tui/detail_screen.py` — `DetailScreen(Screen)` with BINDINGS for `q`→pop, `Escape`→pop, `r`→refresh, `?`→help, `o`→open_browser, `d`→mark_done
- [x] 7.3 Add `Enter` binding to `NotificationList` or `TriageApp` that calls `self.app.push_screen(DetailScreen(...))`
- [x] 7.4 Write failing tests for context-aware `q` — verify `q` quits from main list, `q` pops screen from detail view
- [x] 7.5 Write failing tests for context-aware `Escape` — verify `Escape` clears filter in list view (with active filter), pops screen in detail view
- [x] 7.6 Write failing tests for context-aware `r` — verify `r` refreshes list in main view, refreshes PR data in detail view
- [x] 7.7 Verify all context-aware keybindings work via Textual's screen-level BINDINGS mechanism
- [x] 7.8 Run ruff format, ruff check, mypy on `detail_screen.py` and `app.py`

## 8. Tabbed PR Detail View

- [x] 8.1 Write failing TUI snapshot tests for tabbed layout — three tabs labeled "Description", "Conversations", "Files Changed", number key switching
- [x] 8.2 Implement `TabbedContent` with three `TabPane`s in `DetailScreen.compose()` for PR notifications
- [x] 8.3 Implement number key bindings (`1`, `2`, `3`) to activate corresponding tabs
- [x] 8.4 Write failing tests for issue detail view — single scrollable view with title, author, labels, description, comments (no tabs)
- [x] 8.5 Implement issue/other notification detail layout in `DetailScreen` — single pane with description and comments
- [x] 8.6 Run ruff format, ruff check, mypy on `detail_screen.py`

## 9. Description Tab

- [x] 9.1 Write failing TUI snapshot tests for Description tab — PR title, author, labels as badges, Markdown description, empty description, no labels
- [x] 9.2 Implement `src/forge_triage/tui/tabs/description.py` — widget composing title, author, labels, and Markdown-rendered body
- [x] 9.3 Wire Description tab to load PR metadata via `FetchPRDetailRequest` on detail screen open, show loading indicator during fetch
- [x] 9.4 Write failing tests for loading and error states — loading indicator, fetch error with retry prompt
- [x] 9.5 Implement loading and error states in Description tab
- [x] 9.6 Run ruff format, ruff check, mypy on `description.py`

## 10. Conversations Tab

- [x] 10.1 Write failing TUI snapshot tests for threaded conversations — unresolved threads with replies, resolved threads hidden, empty state
- [x] 10.2 Implement `src/forge_triage/tui/tabs/conversations.py` — render review threads with file path/line reference, initial comment, replies, author, timestamp, light Markdown formatting
- [x] 10.3 Write failing tests for lazy loading — Conversations tab fetches data on first activation, shows loading indicator, uses cache on subsequent activation
- [x] 10.4 Implement lazy loading in Conversations tab — post `FetchPRDetailRequest` on first activation, render from DB cache
- [x] 10.5 Write failing tests for resolved thread toggle — hidden by default, toggle key shows/hides resolved threads
- [x] 10.6 Implement resolved thread toggle with dimmed styling for resolved threads
- [x] 10.7 Write failing tests for thread navigation — `j`/`k` moves focus between threads, highlight current thread
- [x] 10.8 Implement thread navigation with focus highlighting
- [x] 10.9 Run ruff format, ruff check, mypy on `conversations.py`

## 11. Diff View Widget

- [x] 11.1 Write failing unit tests for diff hunk parsing — parse unified diff patch text into structured hunks with line numbers, added/removed/context classification
- [x] 11.2 Implement diff parsing logic in `src/forge_triage/tui/widgets/diff_view.py` — parse GitHub patch format into renderable hunk structures
- [x] 11.3 Write failing tests for syntax-highlighted diff rendering — verify language detection from filename, green/red backgrounds on added/removed lines, line numbers in gutter
- [x] 11.4 Implement diff rendering using Rich `Syntax` for language highlighting with diff-colored backgrounds
- [x] 11.5 Write failing tests for review comment interpolation — comments inserted at correct line positions, multiple comments on same line in chronological order, resolved comments hidden
- [x] 11.6 Implement review comment interpolation in diff rendering — insert styled comment blocks between diff lines at the associated line positions
- [x] 11.7 Write failing tests for edge cases — binary files ("Binary file not shown"), truncated patches, renamed files showing old/new names, empty patches
- [x] 11.8 Handle edge cases in diff rendering
- [x] 11.9 Run ruff format, ruff check, mypy on `diff_view.py`

## 12. Files Changed Tab with Sidebar

- [x] 12.1 Write failing TUI snapshot tests for Files Changed tab — file sidebar with icons and counts, diff view, sidebar collapsed state
- [x] 12.2 Implement `src/forge_triage/tui/tabs/files_changed.py` — layout with `ListView` sidebar and diff view pane
- [x] 12.3 Write failing tests for lazy loading — Files Changed tab fetches files on first activation, shows loading indicator, uses cache on re-activation
- [x] 12.4 Implement lazy loading in Files Changed tab — post request on first activation, render from `pr_files` cache
- [x] 12.5 Write failing tests for file navigation — selecting file in sidebar scrolls diff to that file's section
- [x] 12.6 Implement sidebar file selection → diff scroll navigation
- [x] 12.7 Write failing tests for sidebar toggle — `b` key toggles sidebar visibility, diff view fills full width when sidebar hidden
- [x] 12.8 Implement sidebar toggle with `b` keybinding
- [x] 12.9 Write failing tests for diff scrolling — `j`/`k` scroll diff view, scrolling past file boundary continues to next file
- [x] 12.10 Implement diff view scrolling
- [x] 12.11 Run ruff format, ruff check, mypy on `files_changed.py`

## 13. Command Palette & Review Actions

- [x] 13.1 Write failing TUI snapshot tests for command palette — modal overlay with filterable action list, global actions, thread-context actions
- [x] 13.2 Implement `src/forge_triage/tui/widgets/command_palette.py` — modal screen with `OptionList` or `Input` + filtered `ListView`, context-dependent action list
- [x] 13.3 Write failing tests for action dispatch — selecting "Approve" posts `SubmitReviewRequest`, "Request Changes" opens editor then posts, "Reply" opens editor then posts `PostReviewCommentRequest`, "Resolve" posts `ResolveThreadRequest`
- [x] 13.4 Wire command palette actions to backend message queue
- [x] 13.5 Write failing tests for command palette keybinding — `:` or `Ctrl+p` opens palette, `Escape` dismisses, typing filters actions
- [x] 13.6 Implement command palette keybinding in `DetailScreen` BINDINGS
- [x] 13.7 Run ruff format, ruff check, mypy on `command_palette.py`

## 14. Inline Reply Editor

- [x] 14.1 Write failing TUI tests for reply editor — editor appears below thread, `Ctrl+Enter` submits, `Escape` cancels, empty submission blocked
- [x] 14.2 Implement `src/forge_triage/tui/widgets/reply_editor.py` — `TextArea`-based widget with submit/cancel keybindings
- [x] 14.3 Write failing tests for editor key capture — `1`, `2`, `3`, `q` are captured as text input (not navigation) while editor is focused
- [x] 14.4 Verify key capture isolation via Textual's focus system
- [x] 14.5 Write failing tests for reply failure — error notification shown, draft text preserved in editor
- [x] 14.6 Implement error handling with draft preservation in reply editor
- [x] 14.7 Wire reply editor to Conversations tab and Files Changed tab (reply to inline comments)
- [x] 14.8 Run ruff format, ruff check, mypy on `reply_editor.py`

## 15. Context-Aware Help Screen

- [x] 15.1 Write failing TUI snapshot tests for help screen — different keybinding lists shown in main list view vs detail view
- [x] 15.2 Update `src/forge_triage/tui/help_screen.py` — accept active screen context, display keybindings relevant to the current screen
- [x] 15.3 Run ruff format, ruff check, mypy on `help_screen.py`

## 16. Refresh Flow

- [x] 16.1 Write failing integration tests for detail view refresh — `r` in detail view re-fetches all PR data (metadata, reviews, files), invalidates cache, re-renders active tab
- [x] 16.2 Implement refresh action in `DetailScreen` — delete cached data, re-post fetch requests, show loading indicators during refresh
- [x] 16.3 Write failing tests for tab re-fetch after refresh — tabs that were loaded before refresh re-fetch on next activation
- [x] 16.4 Implement lazy-load invalidation on refresh (reset loaded flags on all tabs)
- [x] 16.5 Run ruff format, ruff check, mypy on `detail_screen.py`

## 17. End-to-End Integration & Polish

- [x] 17.1 Write end-to-end TUI integration test — open app, navigate to PR, press Enter, switch tabs, open command palette, go back, verify list state preserved
- [x] 17.2 Write end-to-end test for issue detail view — open app, navigate to issue, press Enter, verify single-pane view with description and comments
- [x] 17.3 Write end-to-end test for review workflow — open PR, reply to thread, approve PR, verify success notifications
- [x] 17.4 Verify all keybinding context scenarios end-to-end — q/Escape/r behavior in each view
- [x] 17.5 Run full test suite, ruff format, ruff check, mypy across all new and modified files
- [x] 17.6 Update `__init__.py` files for new subpackages (`tui/tabs/`, `tui/widgets/`)
- [x] 17.7 Verify Nix build succeeds with new modules and any new dependencies
