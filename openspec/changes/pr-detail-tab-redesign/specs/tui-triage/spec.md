## MODIFIED Requirements

### Requirement: Context-aware keybindings
The system SHALL make the `q`, `Escape`, and `r` keybindings context-aware. Their behavior SHALL depend on which screen is active (main list view vs detail view). In the detail view, `Escape` SHALL also be aware of search state — clearing an active search before navigating back.

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

#### Scenario: Escape in detail view with active search
- **WHEN** the user presses `Escape` in the detail view with an active search (matches present, search input not focused)
- **THEN** the system SHALL clear the search state (not navigate back)

#### Scenario: Escape in detail view without active search
- **WHEN** the user presses `Escape` in the detail view with no active search and no reply editor focused
- **THEN** the system SHALL close the detail view and return to the main list view

#### Scenario: r in main list view
- **WHEN** the user presses `r` in the main list view
- **THEN** the system SHALL refresh the notification list from the database

#### Scenario: r in detail view
- **WHEN** the user presses `r` in the detail view
- **THEN** the system SHALL refresh the currently viewed PR/issue data from the GitHub API

### Requirement: Conversations tab with threaded review discussions
The system SHALL display PR review conversations as threaded discussions in the Conversation tab (combined with the PR description). Each review thread SHALL show the initial comment, all replies, and the thread's resolution state. Resolved threads SHALL be hidden by default. Threads SHALL be displayed in chronological order (oldest first) below the PR description.

#### Scenario: Displaying unresolved threads
- **WHEN** the Conversation tab is active for a PR with review threads
- **THEN** the system SHALL display the PR description at the top, followed by unresolved threads in chronological order, each showing the file path and line reference, the initial comment, and all replies with author and timestamp

#### Scenario: Hiding resolved threads
- **WHEN** the Conversation tab is active and some threads are resolved
- **THEN** the system SHALL hide resolved threads by default

#### Scenario: Toggling resolved thread visibility
- **WHEN** the user presses the resolved thread toggle key in the Conversation tab
- **THEN** the system SHALL show all resolved threads (dimmed or with a "Resolved" indicator) or hide them again if already shown

#### Scenario: PR with no review threads
- **WHEN** the Conversation tab is active for a PR with no review threads
- **THEN** the system SHALL display the PR description followed by "No conversations yet." in dimmed text

#### Scenario: Scrolling through conversations
- **WHEN** the user uses `j`/`k` in the Conversation tab
- **THEN** the system SHALL scroll the content up/down by one line (scrolling through description and threads as a single continuous document)

## Testing

- **Keybinding context tests**: Test that `q` quits from the main list, `q` pops the screen from the detail view, `Escape` clears search in detail view when search is active, `Escape` clears filter in list view, and `Escape` pops the screen from the detail view when no search/filter is active. Test `r` refreshes the list vs refreshes the PR.
- **Conversations tab tests**: Snapshot threaded conversations showing PR description at top followed by threads. Test resolved thread hiding/toggling. Test empty thread state showing description + "No conversations yet."
- **Scroll consistency tests**: Verify `j`/`k` scrolls content in the Conversation tab the same way it moves the cursor in the notification list (consistent vim feel across views).
