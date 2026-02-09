## ADDED Requirements

### Requirement: Inline diff rendering with syntax highlighting
The system SHALL render PR file diffs as inline (unified) diffs with syntax highlighting based on file type and diff coloring (green background for added lines, red background for removed lines). Each file's diff SHALL be displayed with a file header showing the filename, change status (added/modified/deleted/renamed), and line counts (+N / -N).

#### Scenario: Rendering a modified file diff
- **WHEN** the Files Changed tab displays a diff for a modified file
- **THEN** the system SHALL render the diff with syntax highlighting for the file's language, green background for added lines, red background for removed lines, and neutral background for context lines. Line numbers SHALL be displayed in the gutter for both old and new sides.

#### Scenario: Rendering an added file diff
- **WHEN** the Files Changed tab displays a diff for a newly added file
- **THEN** the system SHALL render all lines with green background and a file header indicating "added"

#### Scenario: Rendering a deleted file diff
- **WHEN** the Files Changed tab displays a diff for a deleted file
- **THEN** the system SHALL render all lines with red background and a file header indicating "deleted"

#### Scenario: Rendering a renamed file diff
- **WHEN** the Files Changed tab displays a diff for a renamed file
- **THEN** the system SHALL show the old and new filenames in the header and render any content changes as a normal diff

#### Scenario: Binary file
- **WHEN** the Files Changed tab encounters a binary file (no patch data)
- **THEN** the system SHALL display a "Binary file not shown" message for that file

#### Scenario: Large diff truncation
- **WHEN** a file diff exceeds a display threshold (e.g., the GitHub API returns a truncated patch)
- **THEN** the system SHALL display the available diff content and show a message "Diff truncated. View full diff in browser." with the file's GitHub URL

### Requirement: Review comments displayed inline in diffs
The system SHALL display review comments inline within the diff at the line positions where they were made. Comments SHALL appear as styled blocks between diff lines, showing the comment author, timestamp, and body.

#### Scenario: Review comment at a specific line
- **WHEN** a review comment is associated with a specific line in a file diff
- **THEN** the system SHALL render the comment as a styled block immediately after that line in the diff, showing the author, timestamp, and body with light Markdown formatting

#### Scenario: Multiple comments on the same line
- **WHEN** multiple review comments exist on the same line
- **THEN** the system SHALL display them in chronological order as a threaded conversation block after that line

#### Scenario: Resolved comment thread in diff
- **WHEN** a review comment thread at a line is resolved and resolved threads are hidden
- **THEN** the system SHALL NOT display the comment block in the diff

#### Scenario: Toggling resolved comments in diff
- **WHEN** the user toggles resolved thread visibility
- **THEN** the system SHALL show or hide resolved comment blocks throughout all diffs

### Requirement: File list sidebar
The system SHALL provide a collapsible sidebar in the Files Changed tab listing all changed files with their change type and line counts. Selecting a file in the sidebar SHALL scroll the diff view to that file's section.

#### Scenario: Displaying the file list
- **WHEN** the Files Changed tab is active
- **THEN** the system SHALL display a sidebar listing each changed file with an icon indicating change type (added/modified/deleted/renamed) and counts (+N / -N)

#### Scenario: Navigating to a file via sidebar
- **WHEN** the user selects a file in the sidebar
- **THEN** the system SHALL scroll the diff view to the selected file's diff section and highlight the file header

#### Scenario: Collapsing the sidebar
- **WHEN** the user presses `b` in the Files Changed tab
- **THEN** the system SHALL toggle the file list sidebar visibility, expanding the diff view to fill the full width when the sidebar is hidden

#### Scenario: File list with many files
- **WHEN** the PR has more files than fit in the sidebar
- **THEN** the sidebar SHALL be scrollable independently of the diff view

### Requirement: Diff view scrolling
The system SHALL allow scrolling through the diff view using standard navigation keys (arrow keys, `j`/`k`, Page Up/Page Down).

#### Scenario: Scrolling with j/k
- **WHEN** the user presses `j` or `k` in the Files Changed tab (with no editor active)
- **THEN** the system SHALL scroll the diff view down or up respectively

#### Scenario: Scrolling between files
- **WHEN** the user scrolls past the end of one file's diff
- **THEN** the system SHALL smoothly continue to the next file's diff with its header visible

## Testing

- **Diff rendering unit tests**: Test diff parsing and rendering with sample patches covering added, modified, deleted, and renamed files. Test syntax highlighting for common file types (Python, JavaScript, Nix). Test line numbering accuracy across multiple hunks.
- **Review comment interpolation tests**: Test that review comments are inserted at the correct line positions in the diff. Test multiple comments on the same line. Test resolved comment hiding.
- **TUI snapshot tests**: Snapshot the Files Changed tab with a multi-file diff, file sidebar, and inline review comments. Snapshot with sidebar collapsed.
- **TUI integration tests**: Use `App.run_test()` to verify sidebar selection scrolls to the correct file, `b` toggles sidebar, and `j`/`k` scroll the diff view.
- **Edge case tests**: Test binary files, truncated diffs, empty patches, files with no review comments.
