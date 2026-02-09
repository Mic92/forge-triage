## ADDED Requirements

### Requirement: Command palette for review actions
The system SHALL provide a command palette accessible via a keybinding in the detail view. The palette SHALL list available review actions as a filterable list. Available actions SHALL depend on the current context (focused conversation thread vs global view).

#### Scenario: Opening the command palette
- **WHEN** the user presses the command palette keybinding (`:` or `Ctrl+p`) in the detail view
- **THEN** the system SHALL display a modal palette listing available review actions with a text filter input

#### Scenario: Global review actions
- **WHEN** the command palette is opened without focus on a specific conversation thread
- **THEN** the system SHALL list: "Approve", "Request Changes", "Comment" (submit a general review comment)

#### Scenario: Thread-context review actions
- **WHEN** the command palette is opened while a conversation thread is focused/selected
- **THEN** the system SHALL list: "Reply", "Resolve Thread", "Unresolve Thread" (in addition to global actions)

#### Scenario: Filtering actions
- **WHEN** the user types in the command palette filter input
- **THEN** the system SHALL filter the action list to show only actions matching the typed text

#### Scenario: Dismissing the command palette
- **WHEN** the user presses `Escape` in the command palette
- **THEN** the system SHALL close the palette without performing any action

### Requirement: Reply to review comment
The system SHALL allow the user to reply to a review conversation thread. Replies SHALL be submitted individually (not batched into a pending review).

#### Scenario: Initiating a reply
- **WHEN** the user selects "Reply" from the command palette while a conversation thread is focused
- **THEN** the system SHALL display an inline text area below the thread for composing the reply

#### Scenario: Submitting a reply
- **WHEN** the user presses `Ctrl+Enter` in the reply editor
- **THEN** the system SHALL submit the reply to the GitHub API as an individual comment on the thread, display a success notification, close the editor, and refresh the thread to show the new comment

#### Scenario: Cancelling a reply
- **WHEN** the user presses `Escape` in the reply editor
- **THEN** the system SHALL close the editor and discard the draft text

#### Scenario: Empty reply submission
- **WHEN** the user presses `Ctrl+Enter` with an empty or whitespace-only reply
- **THEN** the system SHALL NOT submit the reply and SHALL display a warning "Reply cannot be empty"

#### Scenario: Reply submission failure
- **WHEN** a reply submission fails (network error, permission denied, thread deleted)
- **THEN** the system SHALL display an error notification with the failure reason and preserve the draft text in the editor so the user can retry

### Requirement: Approve pull request
The system SHALL allow the user to approve a pull request via the command palette.

#### Scenario: Approving a PR
- **WHEN** the user selects "Approve" from the command palette
- **THEN** the system SHALL submit an approval review to the GitHub API and display a success notification "PR approved"

#### Scenario: Approve failure
- **WHEN** approving fails (e.g., user is the PR author, insufficient permissions)
- **THEN** the system SHALL display an error notification with the failure reason

### Requirement: Request changes on pull request
The system SHALL allow the user to request changes on a pull request via the command palette. The user SHALL be prompted to provide a review body describing the requested changes.

#### Scenario: Requesting changes
- **WHEN** the user selects "Request Changes" from the command palette
- **THEN** the system SHALL display an inline text area for the user to describe the requested changes

#### Scenario: Submitting change request
- **WHEN** the user presses `Ctrl+Enter` in the change request editor
- **THEN** the system SHALL submit a "request changes" review with the provided body to the GitHub API and display a success notification

#### Scenario: Empty change request
- **WHEN** the user presses `Ctrl+Enter` with an empty change request body
- **THEN** the system SHALL NOT submit the review and SHALL display a warning "Review body cannot be empty"

### Requirement: Resolve and unresolve conversation threads
The system SHALL allow the user to resolve and unresolve review conversation threads via the command palette.

#### Scenario: Resolving a thread
- **WHEN** the user selects "Resolve Thread" while a conversation thread is focused
- **THEN** the system SHALL call the GitHub API to resolve the thread, display a success notification, and hide the thread from the conversations list (since resolved threads are hidden by default)

#### Scenario: Unresolving a thread
- **WHEN** the user selects "Unresolve Thread" while viewing a resolved thread (resolved threads toggled visible)
- **THEN** the system SHALL call the GitHub API to unresolve the thread and display a success notification

#### Scenario: Resolve/unresolve failure
- **WHEN** resolving or unresolving a thread fails
- **THEN** the system SHALL display an error notification with the failure reason

### Requirement: Inline reply editor
The system SHALL provide an inline multi-line text editor for composing replies and review bodies. The editor SHALL appear below the relevant context (thread for replies, at the bottom for review bodies).

#### Scenario: Editor keybindings
- **WHEN** the inline reply editor is active
- **THEN** the system SHALL support `Ctrl+Enter` to submit, `Escape` to cancel, and standard text editing (cursor movement, selection, paste)

#### Scenario: Editor does not capture navigation keys
- **WHEN** the inline reply editor is active
- **THEN** the keys `1`, `2`, `3`, `q` SHALL be captured by the editor as text input (not interpreted as tab switches or back navigation)

## Testing

- **TUI snapshot tests**: Snapshot the command palette with different action lists (global context vs thread context). Snapshot the inline reply editor below a conversation thread.
- **TUI integration tests**: Use `App.run_test()` to verify the command palette opens and closes, action selection triggers the appropriate editor or API call, and `Ctrl+Enter` / `Escape` work correctly in the editor.
- **Backend integration tests**: Test each review action request/response message with mocked GitHub API responses. Verify success and error paths for approve, request changes, reply, resolve, and unresolve.
- **Edge case tests**: Test empty reply prevention, reply failure with draft preservation, approving own PR error.
