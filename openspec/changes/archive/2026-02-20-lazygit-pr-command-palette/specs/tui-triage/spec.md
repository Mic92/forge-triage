## MODIFIED Requirements

### Requirement: Context-aware keybindings
The system SHALL make the `q`, `Escape`, `r`, and `:` keybindings context-aware. Their
behavior SHALL depend on which screen is active (main list view vs detail view).

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
