## ADDED Requirements

### Requirement: Vim-style line scrolling in detail view
The system SHALL allow the user to scroll the active tab's content using `j` (down one line) and `k` (up one line) in the detail view. These bindings SHALL always scroll the active tab's content area regardless of which widget within the tab has focus.

#### Scenario: Scrolling down with j
- **WHEN** the user presses `j` in the detail view with scrollable content
- **THEN** the system SHALL scroll the active tab's content down by one line

#### Scenario: Scrolling up with k
- **WHEN** the user presses `k` in the detail view with scrollable content
- **THEN** the system SHALL scroll the active tab's content up by one line

#### Scenario: Scrolling at content boundary
- **WHEN** the user presses `j` when already at the bottom of the content, or `k` when already at the top
- **THEN** the system SHALL do nothing (no wrap-around, no error)

#### Scenario: j/k with search input focused
- **WHEN** the user presses `j` or `k` while the search input is focused
- **THEN** the system SHALL type the character into the search input (not scroll)

### Requirement: Jump to top and bottom in detail view
The system SHALL allow the user to jump to the top of the active tab's content using `g` or `Home`, and to the bottom using `G` or `End`.

#### Scenario: Jump to top with g
- **WHEN** the user presses `g` in the detail view
- **THEN** the system SHALL scroll the active tab's content to the very top

#### Scenario: Jump to bottom with G
- **WHEN** the user presses `G` (shift+g) in the detail view
- **THEN** the system SHALL scroll the active tab's content to the very bottom

#### Scenario: Jump to top with Home
- **WHEN** the user presses `Home` in the detail view
- **THEN** the system SHALL scroll the active tab's content to the very top

#### Scenario: Jump to bottom with End
- **WHEN** the user presses `End` in the detail view
- **THEN** the system SHALL scroll the active tab's content to the very bottom

#### Scenario: g/G with search input focused
- **WHEN** the user presses `g` or `G` while the search input is focused
- **THEN** the system SHALL type the character into the search input (not jump)

### Requirement: Half-page scrolling in detail view
The system SHALL allow the user to scroll the active tab's content by half a page using `Ctrl+d` (down) and `Ctrl+u` (up). Half a page SHALL be defined as half the visible height of the content area.

#### Scenario: Half-page scroll down with Ctrl+d
- **WHEN** the user presses `Ctrl+d` in the detail view
- **THEN** the system SHALL scroll the active tab's content down by half the visible height

#### Scenario: Half-page scroll up with Ctrl+u
- **WHEN** the user presses `Ctrl+u` in the detail view
- **THEN** the system SHALL scroll the active tab's content up by half the visible height

#### Scenario: Half-page scroll near boundary
- **WHEN** the user presses `Ctrl+d` with less than half a page remaining below
- **THEN** the system SHALL scroll to the bottom of the content (not beyond)

### Requirement: Text search within active tab
The system SHALL allow the user to search for text within the active tab's content by pressing `/`. The search SHALL be case-insensitive. Matches SHALL be navigable with `n` (next) and `N` (previous). `Escape` SHALL clear the search and hide the search input.

#### Scenario: Opening the search input
- **WHEN** the user presses `/` in the detail view (with no search input active)
- **THEN** the system SHALL display a search input at the bottom of the screen and focus it

#### Scenario: Submitting a search query
- **WHEN** the user types a query in the search input and presses `Enter`
- **THEN** the system SHALL find all case-insensitive matches in the active tab's content, scroll to the first match, and hide the search input (returning focus to the content)

#### Scenario: No matches found
- **WHEN** the user submits a search query that has no matches in the active tab's content
- **THEN** the system SHALL display a notification "No matches found" and hide the search input

#### Scenario: Navigating to next match with n
- **WHEN** the user presses `n` after a search with multiple matches
- **THEN** the system SHALL scroll to the next match, wrapping to the first match after the last

#### Scenario: Navigating to previous match with N
- **WHEN** the user presses `N` (shift+n) after a search with multiple matches
- **THEN** the system SHALL scroll to the previous match, wrapping to the last match before the first

#### Scenario: Clearing the search with Escape
- **WHEN** the user presses `Escape` while the search input is focused
- **THEN** the system SHALL hide the search input and clear the search state (no active matches)

#### Scenario: Escape with active search but input not focused
- **WHEN** the user presses `Escape` in the detail view with an active search (matches highlighted) but the search input is not focused
- **THEN** the system SHALL clear the search state first (not navigate back to the notification list)

#### Scenario: Search persists across tab switches
- **WHEN** the user has an active search and switches to a different tab
- **THEN** the system SHALL clear the search state (each tab has independent search context)

## Testing

- **Scroll integration tests**: Use `App.run_test()` with a pre-populated PR having long content. Verify `j`/`k` change scroll offset by one line, `g`/`G`/`Home`/`End` jump to top/bottom, `Ctrl+d`/`Ctrl+u` scroll by half the viewport height.
- **Search integration tests**: Use `App.run_test()` to verify `/` shows input, `Enter` submits, `n`/`N` cycle matches, `Escape` clears. Test with zero matches, one match, multiple matches, and wrapping.
- **Focus isolation tests**: Verify that `j`/`k`/`g`/`G`/`h`/`l` type characters into the search input when it is focused, and scroll/switch tabs when it is not.
- **Boundary tests**: Test scrolling at top/bottom boundaries, half-page scroll near edges, and search with empty content.
