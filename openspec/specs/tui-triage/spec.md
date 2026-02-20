## Requirements

### Requirement: Split-pane TUI layout
The system SHALL provide a Textual-based TUI with a resizable split-pane layout: a notification list in the upper pane and a preview pane in the lower pane. The split divider SHALL be draggable with the mouse to resize the panes. The preview pane SHALL show the currently highlighted notification's author, description, and labels. CI status SHALL NOT be displayed in the preview pane.

#### Scenario: Launching the TUI
- **WHEN** the user runs `forge-triage`
- **THEN** the system SHALL display a resizable split-pane TUI with the notification list focused, sorted by priority, and the first column showing the subject state as a nerdfont icon (instead of a priority tier icon). The preview pane SHALL show the currently highlighted notification's author, description body (with light Markdown formatting), and labels.

#### Scenario: Navigating the list updates the detail pane
- **WHEN** the user moves the cursor to a different notification in the list
- **THEN** the preview pane SHALL update to show that notification's author, description, and labels from the local database (no network request unless data is not cached)

#### Scenario: Resizing the split pane
- **WHEN** the user drags the divider bar between the notification list and the preview pane
- **THEN** the system SHALL resize the panes proportionally, maintaining a minimum height for each pane

#### Scenario: Empty inbox
- **WHEN** the user launches the TUI with no notifications in the database
- **THEN** the system SHALL display a message indicating the inbox is empty and suggesting to run `forge-triage sync`

### Requirement: Open detail view from notification list
The system SHALL allow the user to press `Enter` on a notification in the list to open a full-screen detail view. The detail view SHALL be pushed as a new screen, replacing the notification list and preview pane.

#### Scenario: Opening a detail view
- **WHEN** the user presses `Enter` on a notification in the list
- **THEN** the system SHALL push a full-screen detail view for that notification, hiding the notification list and preview pane

#### Scenario: Returning from detail view preserves list state
- **WHEN** the user returns from the detail view to the notification list
- **THEN** the notification list SHALL restore its previous cursor position, scroll offset, and any active filter

### Requirement: Context-aware keybindings
The system SHALL make the `q`, `Escape`, `r`, and `:` keybindings context-aware. Their behavior SHALL depend on which screen is active (main list view vs detail view).

#### Scenario: q in main list view
- **WHEN** the user presses `q` in the main list view
- **THEN** the system SHALL quit the application

#### Scenario: q in detail view
- **WHEN** the user presses `q` in the detail view
- **THEN** the system SHALL close the detail view and return to the main list view (NOT quit the application)

#### Scenario: Escape in main list view with active filter
- **WHEN** the user presses `Escape` in the main list view while a text filter is active
- **THEN** the system SHALL clear the filter

#### Scenario: Escape in main list view without active filter
- **WHEN** the user presses `Escape` in the main list view with no active filter
- **THEN** the system SHALL do nothing

#### Scenario: Escape in detail view
- **WHEN** the user presses `Escape` in the detail view (with no reply editor active)
- **THEN** the system SHALL close the detail view and return to the main list view

#### Scenario: r in main list view
- **WHEN** the user presses `r` in the main list view
- **THEN** the system SHALL refresh the notification list from the database

#### Scenario: r in detail view
- **WHEN** the user presses `r` in the detail view
- **THEN** the system SHALL refresh the currently viewed PR/issue data from the GitHub API

#### Scenario: colon in main list view on a PR notification
- **WHEN** the user presses `:` in the main list view with a PR notification highlighted
- **THEN** the system SHALL open the action palette showing user-defined commands

#### Scenario: colon in main list view on a non-PR notification
- **WHEN** the user presses `:` in the main list view with a non-PR notification highlighted
- **THEN** the system SHALL display a "Not a PR" notification and SHALL NOT open the palette

#### Scenario: colon in detail view
- **WHEN** the user presses `:` in the detail view
- **THEN** the system SHALL open the action palette (behaviour defined by the pr-user-commands capability)

### Requirement: Conversations tab with threaded review discussions
The system SHALL display PR review conversations as threaded discussions in the Conversations tab. Each review thread SHALL show the initial comment, all replies, and the thread's resolution state. Resolved threads SHALL be hidden by default.

#### Scenario: Displaying unresolved threads
- **WHEN** the Conversations tab is active for a PR with review threads
- **THEN** the system SHALL display unresolved threads in chronological order, each showing the file path and line reference, the initial comment, and all replies with author and timestamp

#### Scenario: Hiding resolved threads
- **WHEN** the Conversations tab is active and some threads are resolved
- **THEN** the system SHALL hide resolved threads by default

#### Scenario: Toggling resolved thread visibility
- **WHEN** the user presses the resolved thread toggle key in the Conversations tab
- **THEN** the system SHALL show all resolved threads (dimmed or with a "Resolved" indicator) or hide them again if already shown

#### Scenario: PR with no review threads
- **WHEN** the Conversations tab is active for a PR with no review threads
- **THEN** the system SHALL display "No conversations yet." in dimmed text

#### Scenario: Navigating between threads
- **WHEN** the user uses `j`/`k` or arrow keys in the Conversations tab
- **THEN** the system SHALL move focus between conversation threads, highlighting the currently focused thread

## Testing

- **TUI snapshot tests**: Snapshot the resizable split pane at default and custom ratios. Snapshot the preview pane showing author, description, and labels (with and without labels). Verify CI status is NOT shown in the preview pane. Snapshot the notification list with notifications spanning all subject state variants (open/closed issue, open/closed/merged PR, unknown type) to verify correct nerdfont icons and colors in the first column.
- **TUI integration tests**: Use `App.run_test()` to verify `Enter` pushes the detail screen, dragging the divider resizes the panes, and list state is preserved after returning from the detail view. Verify rendered first column matches the expected icon for each row.
- **Keybinding context tests**: Test that `q` quits from the main list, `q` pops the screen from the detail view, `Escape` clears filter in list view, and `Escape` pops the screen from the detail view. Test `r` refreshes the list vs refreshes the PR.
- **Conversations tab tests**: Snapshot threaded conversations with resolved/unresolved threads. Test toggle visibility of resolved threads. Test empty state.
