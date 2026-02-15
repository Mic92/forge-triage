## Context

The `DetailScreen` in `detail_screen.py` currently renders PR notifications with three `TabPane` children inside a `TabbedContent`: Description, Conversations, and Files Changed. Each tab pane wraps a `VerticalScroll` containing either a `Markdown` or `Static` widget. The main notification list already supports `j`/`k` navigation via `DataTable` bindings, but the detail view has no vim-style scrolling — users must use arrow keys or mouse.

Textual's `VerticalScroll` has built-in `Home`/`End` bindings (`action_scroll_home`/`action_scroll_end`) and `PageUp`/`PageDown` bindings (`action_page_up`/`action_page_down`), but no `j`/`k` or half-page scroll support. `TabbedContent` supports `Tab`/`Shift+Tab` for tab switching natively but the detail screen doesn't expose this since bindings are defined at the screen level.

## Goals / Non-Goals

**Goals:**
- Merge Description + Conversations into a single "Conversation" tab matching GitHub's PR layout
- Consistent vim-style scrolling (`j`/`k`/`g`/`G`/`Ctrl+d`/`Ctrl+u`) across all detail view tab content
- Redundant `Home`/`End` bindings for top/bottom alongside `g`/`G`
- Tab switching via `Tab`/`Shift+Tab`, `h`/`l`, and `1`/`2`
- In-tab text search with `/`, `n`/`N` to cycle matches, `Escape` to clear
- Updated help screen reflecting new bindings

**Non-Goals:**
- Thread-level navigation (`n`/`p` to jump between review threads) — deferred; requires refactoring conversations into discrete widgets
- Collapsible thread rendering or inline reply from the Conversation tab
- Changes to the Files Changed tab content rendering (already covered by `pr-diff-view` spec)
- Changes to the main notification list view

## Decisions

### D1: Single Markdown widget for the Conversation tab

**Decision:** Render the combined Conversation tab as a single `Markdown` widget inside a `VerticalScroll`, concatenating the PR metadata/description at the top with review threads below, separated by horizontal rules.

**Rationale:** The current code already renders description and conversations as separate Markdown strings. Combining them into one avoids dealing with multiple scrollable children or focus management within a single tab. The `_render_description_tab` and `_render_conversations_tab` methods merge into a single `_render_conversation_tab` method.

**Alternative considered:** Two widgets (a fixed description header + scrollable thread list). Rejected because it adds layout complexity and the description can be long (should scroll too). GitHub scrolls everything together.

### D2: Scroll bindings on DetailScreen delegating to active VerticalScroll

**Decision:** Define vim scroll bindings (`j`/`k`/`g`/`G`/`Ctrl+d`/`Ctrl+u`) as `Binding` entries on `DetailScreen`. Each action method finds the active tab's `VerticalScroll` child and calls the appropriate scroll method on it.

**Rationale:** Binding at the screen level ensures keys work regardless of which widget has focus within the tab. Textual's `VerticalScroll` already provides `scroll_down()`, `scroll_up()`, `scroll_home()`, `scroll_end()`. For half-page scroll, we call `scroll_relative(y=offset)` where `offset = container.size.height // 2`.

**Alternative considered:** Subclass `VerticalScroll` with custom bindings. Rejected because it requires managing focus — if the `Markdown` widget inside captures focus, the `VerticalScroll` bindings wouldn't fire. Screen-level bindings always work.

### D3: `g`/`G` as single-keystroke top/bottom (no `gg` sequence)

**Decision:** Use `g` (lowercase) for scroll-to-top and `G` (uppercase) for scroll-to-bottom. Also bind `Home`/`End` to the same actions for standard keyboard users.

**Rationale:** Textual has no built-in multi-key sequence support. Implementing `gg` with a timeout adds complexity (timer management, delayed response on single `g`). Single-keystroke `g`/`G` is pragmatic and discoverable. `Home`/`End` are already bound by `VerticalScroll` natively but we add explicit bindings at the screen level for consistency.

**Alternative considered:** Implementing `gg` via `on_key` handler with `set_timer` for a 300-500ms timeout. Deferred — can upgrade later if the single `g` binding conflicts with future features.

### D4: Search overlay within the detail screen

**Decision:** Implement `/` search as a bottom-anchored `Input` widget (similar to the main list's filter input). On submission, scan the active tab's rendered text content for matches, highlight them, and scroll to the first match. `n`/`N` cycle forward/backward through matches. `Escape` clears the search.

**Rationale:** Reuses the same UX pattern as the main list's `/` filter. The `Markdown` widget renders to Rich `Text` objects — we can search the plain text content. Highlighting matches requires updating the rendered content with styled spans around match positions.

**Implementation approach:**
1. `/` shows the search input, captures query text on Enter
2. Extract plain text from the active tab's content widget
3. Find all match positions using `str.find()` in a loop or `re.finditer()`
4. Store match positions as a list, track current index
5. Scroll the `VerticalScroll` to bring the current match into view
6. `n` increments index (wrapping), `N` decrements
7. `Escape` clears search state and hides the input

**Challenge:** Highlighting matches inside `Markdown` content is non-trivial since `Markdown` re-renders from source. For v1, we can scroll to the match position without visual highlighting, then add highlighting as a follow-up. Alternatively, we overlay match indicators in the gutter.

### D5: Tab switching keybindings

**Decision:** Bind `Tab`/`Shift+Tab`, `h`/`l`, and `1`/`2` at the screen level. Each action calls `TabbedContent.active = <tab-id>` to switch tabs.

**Rationale:** `TabbedContent` has built-in `Tab`/`Shift+Tab` support, but since we define screen-level bindings, we need to explicitly handle these. `h`/`l` mirrors vim left/right navigation. `1`/`2` is the existing pattern (just reduced from 3 tabs).

**Note:** `h`/`l` won't conflict with scrolling because tab content scrolls vertically only (`j`/`k`/`g`/`G`). Horizontal navigation is meaningless in the content area.

### D6: Conversation tab content order

**Decision:** Render conversation content in this order:
1. PR title (H1), metadata line (repo, type, reason)
2. Author, branch info, labels
3. Horizontal rule
4. PR body (Markdown)
5. Horizontal rule
6. Review threads in chronological order (oldest first), matching GitHub

**Rationale:** Matches GitHub's PR conversation page layout. Chronological order lets you read the review discussion as a narrative.

## Risks / Trade-offs

**[Risk] `g` key conflict** → Currently `g` is bound to "toggle grouping" in the main list view, but it's unused in the detail screen. No conflict in the detail view. If `g` is needed for other purposes in the detail view later, we may need to move to `gg` with a timeout.

**[Risk] Search highlighting in Markdown** → Textual's `Markdown` widget re-renders from source text, making it hard to inject highlight spans. Mitigation: v1 scrolls to match position without visual highlighting. Follow-up can add highlighting by post-processing the rendered Rich output or switching to a custom widget.

**[Risk] `h`/`l` overlap with text input** → When the search input is focused, `h`/`l` must type characters, not switch tabs. Mitigation: Search input bindings take priority when focused (Textual's focus-based binding resolution handles this — screen bindings only fire when no focused widget consumes the key).

**[Trade-off] Single-keystroke `g` vs authentic `gg`** → We sacrifice vim authenticity for simplicity. Acceptable because this is a TUI app, not a text editor. Users get the same result with one fewer keystroke.

**[Trade-off] Combined Conversation tab loses tab-level separation** → Users can no longer jump directly to "just review threads" without scrolling past the description. Mitigation: `/` search can find thread content quickly. The description is typically short.

## Testing Strategy

### Unit tests
- **Scroll action methods**: Test that `action_scroll_down`, `action_scroll_up`, `action_scroll_to_top`, `action_scroll_to_bottom`, `action_half_page_down`, `action_half_page_up` correctly delegate to the active `VerticalScroll` widget
- **Conversation tab rendering**: Test `_render_conversation_tab` produces correct Markdown combining description + threads in chronological order
- **Search**: Test match finding logic (case-insensitive, multiple matches, wrapping, no matches)

### Integration tests (App.run_test())
- Verify `Enter` on a PR notification pushes `DetailScreen` with 2 tabs (not 3)
- Verify `Tab`/`Shift+Tab` cycles between Conversation and Files Changed
- Verify `h`/`l` switches tabs left/right
- Verify `1`/`2` activates corresponding tabs
- Verify `j`/`k` scrolls the active tab content
- Verify `g`/`G` and `Home`/`End` jump to top/bottom
- Verify `Ctrl+d`/`Ctrl+u` scrolls half-page
- Verify `/` opens search input, `Enter` submits, `n`/`N` cycles, `Escape` clears
- Verify `q`/`Escape` still navigates back (when search is not active)

### Snapshot tests
- Snapshot the 2-tab PR detail view with Conversation tab active
- Snapshot with Files Changed tab active
- Snapshot the updated help screen

### Mocking strategy
- **Real**: SQLite database (pre-populated with test fixtures), Textual widget rendering
- **Mocked**: GitHub API calls (httpx responses) — only relevant for refresh actions
