## Why

The PR detail view currently has three tabs (Description / Conversations / Files Changed), splitting the PR body from review discussion. GitHub uses two tabs — a combined "Conversation" tab and "Files Changed" — which better matches the mental model of reviewing a PR: you read the description and discussion as one narrative, then inspect the code. Additionally, the detail view lacks vim-style scrolling (j/k/G/gg/Ctrl+d/Ctrl+u) and in-tab search, making it inconsistent with the main notification list which already supports j/k navigation.

## What Changes

- **BREAKING**: Merge the "Description" and "Conversations" tabs into a single "Conversation" tab (PR metadata + body at top, review threads below, GitHub-style)
- Remove the standalone "Description" tab — its content moves into the Conversation tab header
- Reduce tab count from 3 to 2: "Conversation" (1) and "Files Changed" (2)
- Add `Tab`/`Shift+Tab` to cycle between tabs
- Add `h`/`l` for left/right tab switching (vim-style)
- Update number keys from `1`/`2`/`3` to `1`/`2`
- Add vim-style scrolling in all tab content areas: `j`/`k` (line), `g`/`G` (top/bottom), `Home`/`End` (top/bottom), `Ctrl+d`/`Ctrl+u` (half-page)
- Add `/` for text search within the current tab's content
- Update help screen to reflect new keybindings

## Capabilities

### New Capabilities
- `detail-vim-scroll`: Vim-style scrolling (j/k/g/G/Home/End/Ctrl+d/Ctrl+u), in-tab search (/ with n/N to cycle matches) for all scrollable content areas in the detail view

### Modified Capabilities
- `pr-detail-view`: Tab layout changes from 3 tabs to 2 tabs; Description and Conversations merge into a single Conversation tab; tab switching adds Tab/Shift+Tab and h/l bindings; number keys update from 1/2/3 to 1/2
- `tui-triage`: Help screen keybinding display updates for the detail view; j/k in detail view now scrolls content instead of being unbound

## Impact

- `src/forge_triage/tui/detail_screen.py` — Major refactor: merge Description+Conversations tab panes, update BINDINGS, add scroll/search actions
- `src/forge_triage/tui/help_screen.py` — Update `_DETAIL_HELP` text with new keybindings
- `tests/test_detail_screen.py` — Update tests for 2-tab layout, new keybindings, scroll behavior
- `openspec/specs/pr-detail-view/spec.md` — Spec update for tab structure and keybindings
- `openspec/specs/tui-triage/spec.md` — Spec update for detail view keybinding consistency
