## Why

The current TUI shows notifications in a fixed split-pane layout with a basic text detail pane that only displays title, metadata, and flat comments. For PRs, users cannot see the author, description, labels, threaded review conversations, or inline code diffs — they must open a browser (`o`) for any meaningful review. This forces constant context-switching between the TUI and GitHub, undermining the tool's value for PR triage. Adding a rich, full-screen detail view with review capabilities makes the TUI a self-contained triage and review workflow.

## What Changes

- **Resizable split pane**: The existing upper/lower split (notification list + detail) becomes draggable so users can resize the preview area. The preview pane shows author, description, and labels (CI status removed from preview).
- **Full-screen detail view**: Pressing `Enter` on any notification opens a full-screen view replacing the list+preview. For PRs this is a tabbed view (Description, Conversations, Files Changed); for issues it shows description and comments.
- **Tabbed navigation**: Number keys `1`, `2`, `3` switch between tabs in the detail view.
- **Threaded conversations**: The Conversations tab shows threaded review discussions. Resolved threads are hidden by default with a toggle to reveal them.
- **Inline diffs with review comments**: The Files Changed tab shows syntax-highlighted inline diffs with review comments displayed at the relevant lines. A collapsible file list sidebar enables navigation between changed files.
- **Review workflow**: A command palette (triggered by a keybinding) provides review actions: reply to comments, approve, request changes, and resolve conversations. Comments are submitted individually (not batched).
- **Inline reply editor**: An inline text area within the TUI for composing replies (no external editor).
- **Context-aware keybindings**: **BREAKING** — `q` and `Escape` become context-aware. At the top-level list, `q` quits and `Escape` clears filter. In the detail view, both go back to the list. `r` refreshes the list in list view and refreshes the entire PR/issue in detail view.
- **Markdown rendering**: Light formatting for PR/issue descriptions and comments — code blocks highlighted, headers bold, but no full Markdown widget rendering.

## Capabilities

### New Capabilities
- `pr-detail-view`: Full-screen tabbed detail view for PRs (Description, Conversations, Files Changed tabs) and a simpler detail view for issues. Covers navigation, tab switching, back navigation, and the view lifecycle.
- `pr-review-actions`: Review workflow actions — reply to comments, approve, request changes, resolve/unresolve conversations via command palette. Individual comment submission. Inline text editor for replies.
- `pr-diff-view`: Syntax-highlighted inline diffs with review comments at relevant lines. File list sidebar for navigation between changed files.
- `github-pr-api`: GitHub API integration for fetching PR details — description, author, labels, review threads, review comments, and file diffs. Covers both REST and GraphQL queries needed to populate the detail view.

### Modified Capabilities
- `tui-triage`: Split-pane layout becomes resizable (draggable divider). Preview pane content changes to show author, description, labels (no CI status). `Enter` opens full-screen detail view. Keybindings become context-aware (`q`, `Escape`, `r` change behavior based on current view).

## Impact

- **Code**: Major changes to `tui/app.py` (keybinding dispatch, screen management), `tui/detail_pane.py` (replaced or heavily extended). New modules for the detail view screens, diff rendering, review actions, and GitHub PR API client.
- **APIs**: New GitHub GraphQL queries for PR reviews, review comments, and file diffs. New REST/GraphQL mutations for posting review comments, approving, requesting changes, resolving threads.
- **Dependencies**: May need `rich-syntax` or Textual's built-in syntax highlighting for diffs. The Textual `TabbedContent` widget for tabs. Potentially a diff parsing library for unified diff rendering.
- **Database**: May need new tables or columns to cache PR review threads, review comments, and diff data locally to avoid repeated API calls.
- **Testing**: Extensive new snapshot tests for the detail view, diff rendering, and review UI. Integration tests for the new GitHub API queries. Keybinding context-awareness needs thorough testing.
