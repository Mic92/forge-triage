## MODIFIED Requirements

### Requirement: Split-pane TUI layout
The system SHALL provide a Textual-based TUI with a split-pane layout: a notification list in the upper pane and a detail/comment view in the lower pane.

#### Scenario: Launching the TUI
- **WHEN** the user runs `forge-triage`
- **THEN** the system SHALL display a split-pane TUI with the notification list focused, sorted by priority, and the first column showing the subject state as a nerdfont icon (instead of a priority tier icon). The detail pane SHALL show the currently highlighted notification's full content including title, metadata, description, and comments.

#### Scenario: Navigating the list updates the detail pane
- **WHEN** the user moves the cursor to a different notification in the list
- **THEN** the detail pane SHALL update to show that notification's full content from the local database (no network request unless comments are not cached)

#### Scenario: Empty inbox
- **WHEN** the user launches the TUI with no notifications in the database
- **THEN** the system SHALL display a message indicating the inbox is empty and suggesting to run `forge-triage sync`

## Testing

- **TUI snapshot tests**: Snapshot the notification list with notifications spanning all subject state variants (open/closed issue, open/closed/merged PR, unknown type) to verify correct nerdfont icons and colors in the first column.
- **TUI integration tests**: Use `App.run_test()` with a pre-populated SQLite database containing notifications with various `subject_type` and `subject_state` values. Verify the rendered first column matches the expected icon for each row.
