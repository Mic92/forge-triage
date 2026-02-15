## MODIFIED Requirements

### Requirement: Full-screen detail view for notifications
The system SHALL provide a full-screen detail view that opens when the user presses `Enter` on a notification in the list. The detail view SHALL replace the notification list and preview pane entirely. For PullRequest notifications, the view SHALL display tabbed content with two tabs: "Conversation" and "Files Changed". The Conversation tab SHALL combine the PR description/metadata with review threads in a single scrollable view (GitHub-style). For Issue notifications, the view SHALL display the description and comments in a single scrollable view.

#### Scenario: Opening a PR detail view
- **WHEN** the user presses `Enter` on a PullRequest notification in the list
- **THEN** the system SHALL display a full-screen detail view with two tabs labeled "Conversation" (1) and "Files Changed" (2), with the Conversation tab active by default

#### Scenario: Opening an Issue detail view
- **WHEN** the user presses `Enter` on an Issue notification in the list
- **THEN** the system SHALL display a full-screen detail view showing the issue title, author, labels, description body, and comments in a single scrollable view

#### Scenario: Opening a detail view for other notification types
- **WHEN** the user presses `Enter` on a notification that is neither a PullRequest nor an Issue
- **THEN** the system SHALL display a full-screen detail view showing the notification title, metadata, and any cached comments

#### Scenario: Loading state
- **WHEN** the detail view opens and PR/issue data has not been fetched yet
- **THEN** the system SHALL display a loading indicator while fetching data from the GitHub API

#### Scenario: Fetch error
- **WHEN** the detail view fails to fetch data from the GitHub API
- **THEN** the system SHALL display an error message with the failure reason and offer the user the option to retry with the refresh key

### Requirement: Tab switching in PR detail view
The system SHALL allow switching between tabs using multiple methods: number keys `1` and `2` corresponding to Conversation and Files Changed respectively, `Tab` and `Shift+Tab` to cycle forward and backward through tabs, and `h` (left/previous) and `l` (right/next) for vim-style tab navigation.

#### Scenario: Switching tabs with number keys
- **WHEN** the user presses `1` or `2` in the PR detail view
- **THEN** the system SHALL activate the corresponding tab (1=Conversation, 2=Files Changed) and display its content

#### Scenario: Cycling tabs with Tab key
- **WHEN** the user presses `Tab` in the PR detail view
- **THEN** the system SHALL switch to the next tab, wrapping from the last tab to the first

#### Scenario: Cycling tabs with Shift+Tab
- **WHEN** the user presses `Shift+Tab` in the PR detail view
- **THEN** the system SHALL switch to the previous tab, wrapping from the first tab to the last

#### Scenario: Switching tabs with h/l
- **WHEN** the user presses `h` in the PR detail view (with no text input focused)
- **THEN** the system SHALL switch to the previous tab (or wrap to last)
- **WHEN** the user presses `l` in the PR detail view (with no text input focused)
- **THEN** the system SHALL switch to the next tab (or wrap to first)

#### Scenario: Tab content is preserved when switching
- **WHEN** the user switches away from a tab and then switches back
- **THEN** the system SHALL restore the tab's scroll position and content state

#### Scenario: h/l with search input focused
- **WHEN** the user presses `h` or `l` while the search input is focused
- **THEN** the system SHALL type the character into the search input (not switch tabs)

### Requirement: Lazy loading of tab content
The system SHALL load tab content lazily — fetching data from the API only when a tab is first activated. The Conversation tab SHALL load its data immediately when the detail view opens. The Files Changed tab SHALL fetch its data on first activation.

#### Scenario: First activation of Files Changed tab
- **WHEN** the user switches to the Files Changed tab for the first time
- **THEN** the system SHALL fetch the PR's changed files from the GitHub API, display a loading indicator during the fetch, and render the diffs once loaded

#### Scenario: Subsequent tab activation uses cached data
- **WHEN** the user switches to a tab that has already been loaded
- **THEN** the system SHALL display the cached content without making additional API calls

### Requirement: Conversation tab content
The Conversation tab SHALL display, in order: the PR title as a top-level heading, metadata (repo, type, reason), author, branch info (head → base), labels (if any), a horizontal rule, the PR description body rendered as Markdown, a horizontal rule, then review threads in chronological order (oldest first). Each review thread SHALL show the file path and line reference, the diff hunk context, the initial comment, and all replies with author and timestamp. Resolved threads SHALL be hidden by default.

#### Scenario: Rendering PR conversation with description and threads
- **WHEN** the Conversation tab is displayed for a PR with a description and review threads
- **THEN** the system SHALL display the PR metadata and description at the top, followed by review threads in chronological order, with each thread showing its file location, diff context, and comments

#### Scenario: PR with no description
- **WHEN** the Conversation tab is displayed for a PR with an empty description body
- **THEN** the system SHALL display the title, author, and labels, show "No description provided." in dimmed text, then display any review threads below

#### Scenario: PR with no labels
- **WHEN** the Conversation tab is displayed for a PR with no labels
- **THEN** the system SHALL omit the labels section entirely (no empty "Labels:" line)

#### Scenario: PR with no review threads
- **WHEN** the Conversation tab is displayed for a PR with no review threads
- **THEN** the system SHALL display the PR metadata and description, followed by "No conversations yet." in dimmed text

#### Scenario: Hiding resolved threads
- **WHEN** the Conversation tab is displayed and some threads are resolved
- **THEN** the system SHALL hide resolved threads by default

#### Scenario: Toggling resolved thread visibility
- **WHEN** the user presses the resolved thread toggle key in the Conversation tab
- **THEN** the system SHALL show all resolved threads (dimmed or with a "Resolved" indicator) or hide them again if already shown

### Requirement: Back navigation from detail view
The system SHALL allow the user to return to the notification list by pressing `q` or `Escape` in the detail view. The notification list SHALL be restored to its previous state (scroll position, selected item, filter). When a search is active (matches present but search input not focused), `Escape` SHALL clear the search instead of navigating back.

#### Scenario: Pressing q in detail view
- **WHEN** the user presses `q` in the detail view
- **THEN** the system SHALL close the detail view and return to the notification list with the previously selected notification still highlighted

#### Scenario: Pressing Escape in detail view with no active search
- **WHEN** the user presses `Escape` in the detail view with no search input focused and no active search
- **THEN** the system SHALL close the detail view and return to the notification list with the previously selected notification still highlighted

#### Scenario: Escape while reply editor is active
- **WHEN** the user presses `Escape` while the inline reply editor is focused
- **THEN** the system SHALL close the reply editor (not navigate back to the list)

#### Scenario: Escape with active search
- **WHEN** the user presses `Escape` in the detail view with an active search (search input not focused)
- **THEN** the system SHALL clear the search state first, requiring a second `Escape` to navigate back

### Requirement: Refresh detail view
The system SHALL allow the user to press `r` in the detail view to refresh all PR/issue data from the GitHub API.

#### Scenario: Refreshing the detail view
- **WHEN** the user presses `r` in the detail view
- **THEN** the system SHALL re-fetch the PR/issue metadata, review threads, and file diffs from the GitHub API and update all tabs with fresh data

#### Scenario: Refresh clears lazy-load state
- **WHEN** the user presses `r` and some tabs have not been loaded yet
- **THEN** the system SHALL invalidate all cached data so that tabs re-fetch when next activated

### Requirement: Help screen shows context-aware keybindings
The system SHALL display keybindings relevant to the current view when the user presses `?`. In the detail view, the help screen SHALL show detail-view-specific keybindings including tab switching, scrolling, search, back navigation, refresh, and review actions.

#### Scenario: Help in detail view
- **WHEN** the user presses `?` in the detail view
- **THEN** the system SHALL display a help overlay listing keybindings for: tab switching (1/2, Tab/Shift+Tab, h/l), scrolling (j/k, g/G, Home/End, Ctrl+d/Ctrl+u), search (/, n/N, Escape), back navigation (q/Escape), refresh (r), open in browser (o), mark done (d), and review actions (command palette trigger)

## REMOVED Requirements

### Requirement: Description tab content
**Reason**: The standalone Description tab is removed. Its content (PR title, author, labels, description body with Markdown formatting) is now rendered as the header section of the combined Conversation tab.
**Migration**: All description content is accessible at the top of the Conversation tab. No user action required.

## Testing

- **TUI snapshot tests**: Snapshot the 2-tab PR detail view with Conversation tab active showing PR metadata + description + review threads. Snapshot with Files Changed tab active. Test with PRs having descriptions, labels, no labels, no threads, and resolved threads.
- **TUI integration tests**: Use `App.run_test()` to verify `Enter` pushes the detail screen with 2 tabs (not 3), `q` and `Escape` pop it, number keys `1`/`2` switch tabs, `Tab`/`Shift+Tab` cycle tabs, `h`/`l` switch tabs. Verify the notification list is restored after returning.
- **Tab switching tests**: Verify all tab switching methods (1/2, Tab/Shift+Tab, h/l) activate the correct tab. Verify h/l type characters when search input is focused.
- **Conversation tab tests**: Verify the combined tab renders description at top and threads below in chronological order. Test resolved thread hiding/toggling. Test empty states (no description, no threads, no labels).
- **Lazy loading tests**: Verify that Files Changed tab shows a loading indicator on first access and uses cached data on subsequent access. Verify refresh invalidates cache.
- **Back navigation tests**: Verify Escape clears active search first, then navigates back on second press. Verify Escape closes reply editor without navigating back.
