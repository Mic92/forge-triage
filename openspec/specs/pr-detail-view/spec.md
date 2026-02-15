## ADDED Requirements

### Requirement: Full-screen detail view for notifications
The system SHALL provide a full-screen detail view that opens when the user presses `Enter` on a notification in the list. The detail view SHALL replace the notification list and preview pane entirely. For PullRequest notifications, the view SHALL display tabbed content with Description, Conversations, and Files Changed tabs. For Issue notifications, the view SHALL display the description and comments in a single scrollable view.

#### Scenario: Opening a PR detail view
- **WHEN** the user presses `Enter` on a PullRequest notification in the list
- **THEN** the system SHALL display a full-screen detail view with three tabs labeled "Description" (1), "Conversations" (2), and "Files Changed" (3), with the Description tab active by default

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
The system SHALL allow switching between tabs using number keys `1`, `2`, and `3` corresponding to Description, Conversations, and Files Changed respectively.

#### Scenario: Switching tabs with number keys
- **WHEN** the user presses `1`, `2`, or `3` in the PR detail view
- **THEN** the system SHALL activate the corresponding tab (1=Description, 2=Conversations, 3=Files Changed) and display its content

#### Scenario: Tab content is preserved when switching
- **WHEN** the user switches away from a tab and then switches back
- **THEN** the system SHALL restore the tab's scroll position and content state

### Requirement: Automatic background loading of PR data
The system SHALL automatically fetch PR details (metadata, review threads, and changed files) in the background when the detail view opens for a PullRequest notification. If cached data exists, it SHALL be displayed immediately while the background fetch runs. All tabs SHALL update automatically when the fetch completes.

#### Scenario: Opening a PR with no cached data
- **WHEN** the user opens a PR detail view and no cached data exists
- **THEN** the system SHALL display a loading indicator ("⏳ Loading PR details…") in the Conversation tab and Files Changed tab while fetching data in the background

#### Scenario: Opening a PR with cached data
- **WHEN** the user opens a PR detail view and cached data exists in the database
- **THEN** the system SHALL immediately render the cached data and simultaneously fetch fresh data in the background, re-rendering all tabs when the fetch completes

#### Scenario: Subsequent tab activation uses loaded data
- **WHEN** the user switches to a tab after PR data has been fetched
- **THEN** the system SHALL display the loaded content without making additional API calls

### Requirement: Back navigation from detail view
The system SHALL allow the user to return to the notification list by pressing `q` or `Escape` in the detail view. The notification list SHALL be restored to its previous state (scroll position, selected item, filter).

#### Scenario: Pressing q in detail view
- **WHEN** the user presses `q` in the detail view
- **THEN** the system SHALL close the detail view and return to the notification list with the previously selected notification still highlighted

#### Scenario: Pressing Escape in detail view
- **WHEN** the user presses `Escape` in the detail view
- **THEN** the system SHALL close the detail view and return to the notification list with the previously selected notification still highlighted

#### Scenario: Escape while reply editor is active
- **WHEN** the user presses `Escape` while the inline reply editor is focused
- **THEN** the system SHALL close the reply editor (not navigate back to the list)

### Requirement: Refresh detail view
The system SHALL allow the user to press `r` in the detail view to refresh all PR/issue data from the GitHub API.

#### Scenario: Refreshing the detail view
- **WHEN** the user presses `r` in the detail view
- **THEN** the system SHALL re-fetch the PR/issue metadata, review threads, and file diffs from the GitHub API and update all tabs with fresh data

#### Scenario: Refresh clears lazy-load state
- **WHEN** the user presses `r` and some tabs have not been loaded yet
- **THEN** the system SHALL invalidate all cached data so that tabs re-fetch when next activated

### Requirement: Description tab content
The Description tab SHALL display the PR title, author, labels, and description body. The description body SHALL be rendered with light Markdown formatting: headings as bold text, inline code styled, fenced code blocks with syntax highlighting, bold and italic markup, and URLs as clickable links.

#### Scenario: Rendering PR description
- **WHEN** the Description tab is displayed for a PR with a title, author, labels, and Markdown description body
- **THEN** the system SHALL display the title as a bold heading, the author name, labels as styled badges, and the description body with light Markdown formatting

#### Scenario: PR with no description
- **WHEN** the Description tab is displayed for a PR with an empty description body
- **THEN** the system SHALL display the title, author, and labels, and show "No description provided." in dimmed text where the body would be

#### Scenario: PR with no labels
- **WHEN** the Description tab is displayed for a PR with no labels
- **THEN** the system SHALL omit the labels section entirely (no empty "Labels:" line)

### Requirement: Help screen shows context-aware keybindings
The system SHALL display keybindings relevant to the current view when the user presses `?`. In the detail view, the help screen SHALL show detail-view-specific keybindings (tab switching, back navigation, refresh, review actions) instead of the main list keybindings.

#### Scenario: Help in detail view
- **WHEN** the user presses `?` in the detail view
- **THEN** the system SHALL display a help overlay listing keybindings for: tab switching (1/2/3), back navigation (q/Escape), refresh (r), open in browser (o), mark done (d), and review actions (command palette trigger)

## Testing

- **TUI snapshot tests**: Snapshot the PR detail view with each tab active using pre-populated DB data. Verify tab labels, keybinding indicators, and content layout. Test with PRs having descriptions, labels, and no labels.
- **TUI integration tests**: Use `App.run_test()` to verify `Enter` pushes the detail screen, `q` and `Escape` pop it, and number keys switch tabs. Verify the notification list is restored after returning.
- **Lazy loading tests**: Verify that Conversations and Files Changed tabs show a loading indicator on first access and use cached data on subsequent access. Verify refresh invalidates cache.
- **Light Markdown tests**: Unit-test the Markdown-to-Rich-markup converter with headings, code blocks, bold, italic, inline code, and URLs.
