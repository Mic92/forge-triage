## 1. Merge Description + Conversations into Conversation tab

- [x] 1.1 Write failing test: `test_pr_detail_has_two_tabs` — PR detail view has 2 tabs ("Conversation", "Files Changed"), Conversation tab active by default, renders PR metadata (title, author, branch, labels) followed by description body followed by review threads in chronological order.
- [x] 1.2 Write failing test: `test_conversation_tab_edge_cases` — no description shows "No description provided.", no labels omits "Labels:" line, no review threads shows "No conversations yet." after description.
- [x] 1.3 Implement: Refactor `DetailScreen.compose()` to create 2 `TabPane`s — "Conversation" (`tab-conversation`) and "Files Changed" (`tab-files`). Merge `_render_description_tab` and `_render_conversations_tab` into `_render_conversation_tab`. Remove old 3-tab structure and dead code (`tab-description`, `tab-conversations`, `#description-content`, `#conversations-content`).
- [x] 1.4 Update `test_conversation_tab_shows_diff_hunk` to use new widget ID (`#conversation-content`) and no tab switch (Conversation is now tab 1).
- [x] 1.5 Run ruff check, ruff format, mypy — fix any issues.

## 2. Tab switching keybindings

- [x] 2.1 Write failing test: `test_tab_switching_all_methods` — `1`/`2` activate Conversation/Files Changed, `Tab` cycles forward (wraps), `Shift+Tab` cycles backward (wraps), `h`/`l` switch left/right.
- [x] 2.2 Implement: Update `BINDINGS` — replace `1`/`2`/`3` with `1`/`2`, add `tab`/`shift+tab`/`h`/`l`. Implement `action_tab_next`, `action_tab_prev`, `action_tab_1`, `action_tab_2`. Remove `action_tab_3`.
- [x] 2.3 Run ruff check, ruff format, mypy — fix any issues.

## 3. Vim-style scrolling (j/k/g/G/Home/End/Ctrl+d/Ctrl+u)

- [x] 3.1 Write failing test: `test_vim_scroll_all_keys` — seed long content. `j` increases scroll_y, `k` decreases it, `G` and `End` jump to max_scroll_y, `g` and `Home` jump to 0, `Ctrl+d` scrolls down ~half viewport, `Ctrl+u` scrolls back up ~half viewport.
- [x] 3.2 Write failing test: `test_scroll_boundary_behavior` — `j` at bottom doesn't change scroll_y, `k` at top doesn't change scroll_y, `Ctrl+d` near bottom lands at max_scroll_y (no overshoot).
- [x] 3.3 Implement: Add `j`/`k`/`g`/`G`/`home`/`end`/`ctrl+d`/`ctrl+u` bindings to `DetailScreen.BINDINGS`. Implement `_get_active_scroll` helper. Implement action methods delegating to `scroll_down()`/`scroll_up()`/`scroll_home()`/`scroll_end()`/`scroll_relative()` on active `VerticalScroll`.
- [x] 3.4 Run ruff check, ruff format, mypy — fix any issues.

## 4. In-tab text search

- [x] 4.1 Write failing test: `test_search_basic_flow` — `/` shows search input, type query + `Enter` scrolls to first match, search input hides. Query with no matches shows "No matches found" notification and hides input.
- [x] 4.2 Write failing test: `test_search_navigation` — with multiple matches: `n` scrolls to next match (wraps from last to first), `N` scrolls to previous match (wraps from first to last).
- [x] 4.3 Write failing test: `test_search_escape_behavior` — `Escape` while search input focused hides input and clears search. `Escape` with active search (input not focused) clears search state but does NOT pop screen. Second `Escape` pops screen. Switching tabs clears search state.
- [x] 4.4 Implement: Add search `Input` widget (hidden, docked bottom). Add `/`/`n`/`N` bindings. On submit: extract plain text, find matches with `re.finditer()` (case-insensitive), store match line positions, scroll to first. Track `search_matches`/`search_index`. Update `action_go_back` to clear search before popping. Clear search on tab switch.
- [x] 4.5 Run ruff check, ruff format, mypy — fix any issues.

## 5. Focus isolation

- [x] 5.1 Write failing test: `test_keys_type_into_search_input` — with search input focused, pressing `j`, `k`, `g`, `G`, `h`, `l` types characters into input (does not scroll or switch tabs).
- [x] 5.2 Verify Textual's focus-based binding resolution handles this. If not, add `on_key` guards or adjust binding priority.
- [x] 5.3 Run ruff check, ruff format, mypy — fix any issues.

## 6. Help screen update

- [x] 6.1 Write failing test: `test_detail_help_shows_new_keybindings` — help text contains `j`/`k`, `g`/`G`, `Home`/`End`, `Ctrl+d`/`Ctrl+u`, `Tab`/`Shift+Tab`, `h`/`l`, `/`, `n`/`N`. Does NOT reference tab `3`.
- [x] 6.2 Implement: Update `_DETAIL_HELP` in `help_screen.py`.
- [x] 6.3 Run ruff check, ruff format, mypy — fix any issues.

## 7. Final integration and cleanup

- [x] 7.1 Run full test suite — all existing tests pass.
- [x] 7.2 Manual smoke test: 2 tabs, all switching methods, all scroll keys, search with /n/N, Escape clears search then navigates back.
- [x] 7.3 Run ruff check, ruff format, mypy — final clean pass.
- [x] 7.4 Commit with descriptive message.
