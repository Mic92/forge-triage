## ADDED Requirements

### Requirement: Split-pane TUI layout
The system SHALL provide a Textual-based TUI with a split-pane layout: a notification list in the upper pane and a detail/comment view in the lower pane.

#### Scenario: Launching the TUI
- **WHEN** the user runs `forge-triage`
- **THEN** the system SHALL display a split-pane TUI with the notification list focused, sorted by priority, and the detail pane showing the currently highlighted notification's full content including title, metadata, description, and comments

#### Scenario: Navigating the list updates the detail pane
- **WHEN** the user moves the cursor to a different notification in the list
- **THEN** the detail pane SHALL update to show that notification's full content from the local database (no network request unless comments are not cached)

#### Scenario: Empty inbox
- **WHEN** the user launches the TUI with no notifications in the database
- **THEN** the system SHALL display a message indicating the inbox is empty and suggesting to run `forge-triage sync`

### Requirement: Keyboard navigation
The system SHALL support keyboard-driven navigation for efficient triage.

#### Scenario: Vim-style navigation
- **WHEN** the user presses `j` or `↓`
- **THEN** the cursor moves to the next notification in the list

#### Scenario: Vim-style navigation up
- **WHEN** the user presses `k` or `↑`
- **THEN** the cursor moves to the previous notification in the list

#### Scenario: Scroll detail pane
- **WHEN** the detail pane is focused and the user scrolls
- **THEN** the detail content SHALL scroll to reveal more of the comment thread

#### Scenario: Quit
- **WHEN** the user presses `q`
- **THEN** the TUI SHALL exit

### Requirement: Mark notification as done
The system SHALL allow the user to mark notifications as done from the TUI. The TUI posts a request to the backend worker, which handles the GitHub API call and database deletion. The TUI never calls the GitHub API directly.

#### Scenario: Mark single notification done
- **WHEN** the user presses `d` on a highlighted notification
- **THEN** the notification SHALL be optimistically removed from the list and the cursor SHALL move to the next notification. The backend worker SHALL mark it as read on GitHub and delete it from the local database. On success, the removal is confirmed.

#### Scenario: Mark done with API failure
- **WHEN** the user presses `d` and the backend reports that the GitHub API call failed
- **THEN** the system SHALL roll the notification back into the list and display an error message in the TUI

### Requirement: Open notification in browser
The system SHALL allow the user to open the notification's URL in the default browser.

#### Scenario: Open in browser
- **WHEN** the user presses `o` on a highlighted notification
- **THEN** the system SHALL open the notification's subject URL in the default web browser

### Requirement: Filter notifications
The system SHALL allow the user to filter the notification list interactively.

#### Scenario: Text filter
- **WHEN** the user presses `/` and types a filter string
- **THEN** the list SHALL show only notifications whose title, repo name, or author matches the filter string (case-insensitive)

#### Scenario: Filter by reason
- **WHEN** the user presses `r` and selects a reason (e.g., review_requested, mention, subscribed)
- **THEN** the list SHALL show only notifications with that reason

#### Scenario: Clear filter
- **WHEN** the user presses `Escape` while a filter is active
- **THEN** the filter SHALL be cleared and all notifications shown

### Requirement: Group notifications by repository
The system SHALL allow grouping the notification list by repository.

#### Scenario: Toggle grouping
- **WHEN** the user presses `g`
- **THEN** the notification list SHALL toggle between flat (sorted by priority) and grouped-by-repo views with collapsible repo headers

#### Scenario: Collapse a repo group
- **WHEN** the list is grouped by repo and the user presses `Enter` on a repo header
- **THEN** that repo's notifications SHALL toggle between collapsed and expanded

### Requirement: Bulk selection and bulk dismiss
The system SHALL support selecting multiple notifications and performing bulk actions.

#### Scenario: Toggle selection
- **WHEN** the user presses `x` on a notification
- **THEN** that notification SHALL be toggled as selected (visually marked)

#### Scenario: Select all visible
- **WHEN** the user presses `*`
- **THEN** all currently visible (filtered) notifications SHALL be selected

#### Scenario: Bulk done
- **WHEN** the user presses `D` with one or more notifications selected
- **THEN** all selected notifications SHALL be optimistically removed from the list and a bulk done request SHALL be posted to the backend worker, which marks them as read on GitHub and deletes them from the local database

### Requirement: Lazy-load comments on preview
The system SHALL request comment fetching via the backend worker when a notification without cached comments is previewed. The TUI never calls the GitHub API directly.

#### Scenario: Previewing a notification without cached comments
- **WHEN** the user navigates to a notification that has no cached comments
- **THEN** the detail pane SHALL show a loading indicator, the TUI SHALL post a fetch request to the backend worker, and upon receiving the response SHALL cache and display the comments

#### Scenario: Previewing a notification with cached comments
- **WHEN** the user navigates to a notification that has cached comments
- **THEN** the detail pane SHALL display the cached comments immediately from the local database with no loading delay and no backend request

### Requirement: Background pre-load after triage
The system SHALL pre-load comments for new top-priority notifications after the user marks items as done, so comments are ready before the user navigates to them.

#### Scenario: Pre-load triggered after marking done
- **WHEN** the user marks one or more notifications as done in the TUI and the backend confirms success
- **THEN** the TUI SHALL post a pre-load request to the backend worker for the top N notifications (by priority) that have `comments_loaded = 0`, and the backend SHALL fetch their comments without blocking the UI

#### Scenario: Background pre-load does not interrupt the user
- **WHEN** background comment pre-loading is in progress
- **THEN** the user SHALL be able to continue navigating, filtering, and triaging without delay

### Requirement: Highlight new comments
The system SHALL visually distinguish comments that arrived since the user last viewed a notification.

#### Scenario: New comments since last view
- **WHEN** the user views a notification that has new comments since the last time they viewed it
- **THEN** new comments SHALL be visually highlighted (e.g., different color or marker)

#### Scenario: First view
- **WHEN** the user views a notification for the first time
- **THEN** all comments SHALL be shown without the "new" highlight

### Requirement: Help overlay
The system SHALL provide a help screen showing available keybindings.

#### Scenario: Show help
- **WHEN** the user presses `?`
- **THEN** a modal overlay SHALL appear listing all keybindings and their descriptions

#### Scenario: Dismiss help
- **WHEN** the help overlay is showing and the user presses `?` or `Escape`
- **THEN** the overlay SHALL be dismissed

## Testing

- **Snapshot tests**: Use Textual's snapshot testing to verify visual layout of the split-pane, help overlay, loading states, filter modes, grouped view, and selection indicators. Snapshots are the primary way to catch visual regressions.
- **TUI integration tests**: Use Textual's `App.run_test()` with `pilot.press()` and a fake backend (canned response queue) — no network mocking needed. Verify that keypresses produce the correct request messages and that response messages update widgets correctly. Pre-populate with a real SQLite database.
- **Backend integration tests**: Test the backend worker independently — post request messages, verify GitHub API mock called correctly, verify response messages posted with correct data.
