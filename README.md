# forge-triage

A fast terminal UI for triaging GitHub notifications. Prioritizes what
needs your attention, lets you triage with vim-style keybindings, and
keeps everything in a local SQLite database for instant access.

![forge-triage TUI screenshot](https://github.com/Mic92/forge-triage/releases/download/assets/forge-triage-tui.png)

```
 ⭘                                                   forge-triage
    Repo                                            Title
   NixOS/nixpkgs                                   bcc.libbpf-tools: init at 0.35.0
   NixOS/nixpkgs                                   python3Packages.python-engineio: 4.13.0 -> 4.13.1
   NixOS/nixpkgs                                   Module maintainer review requests and `meta.teams` for modules
   NixOS/infra                                     builders: bump max-silent-time to 4h
   NixOS/nixpkgs                                   nvme-cli: 2.15 -> 2.16
   NixOS/nixpkgs                                   nixVersions.nix_2_33: 2.33.1 -> 2.33.2
   NixOS/nixpkgs                                   [Backport release-25.11] ci: pin @actions/artifact to 5.0.3
   NixOS/nixpkgs                                   top-level/packages-info: pre-evaluate output paths
   NixOS/nixpkgs                                   home-assistant: 2026.1.3 -> 2026.2.0
   NixOS/infra                                     Update github/codeql-action digest to 45cbd0c
   NixOS/nixos-hardware                            starfive visionfive2: cleanup kernel requirements
────────────────────────────────────────────────────────────────────────────────────────────────────
  bcc.libbpf-tools: init at 0.35.0
  NixOS/nixpkgs  •  PullRequest  •  review_requested
  CI: success

 q Quit  ? Help  d Done  o Open  / Filter  r Refresh  : Actions
```

## Features

- **Priority-based sorting** — Notifications are scored and sorted into
  tiers so the most important items surface first:
  - 🔴 **Blocking**: review requests (boosted further when CI passes)
  - 🟡 **Action**: direct mentions, assignments, your own PR with failing CI
  - ⚪ **FYI**: team mentions, subscriptions, everything else
- **Split-pane TUI** — Upper pane lists notifications with nerdfont
  state icons (open/closed/merged); lower pane shows metadata, CI status,
  and comments.
- **Full-screen detail view** — Press `Enter` to open a PR or issue in a
  dedicated screen. PRs get a two-tab layout (Conversation / Files Changed)
  with vim-style scrolling and in-screen text search.
- **Command palette** — Press `:` on any PR to run built-in review actions
  (Approve, Request Changes, Refresh) or your own user-defined commands.
- **User-defined commands** — Configure arbitrary commands in
  `~/.config/forge-triage/commands.toml` with template variables
  (`{pr_number}`, `{branch}`, `{repo}`, …), optional `cwd`, and `env` overrides.
- **Vim keybindings** — `j`/`k` navigation, `d` to mark done, `o` to
  open in browser, `/` to filter, `g`/`G` to jump, `Ctrl+d`/`Ctrl+u` to
  scroll half-page.
- **Local cache** — All data is stored locally for instant startup and offline browsing.
- **CLI subcommands** — `sync`, `ls`, `stats`, `done`, and raw `sql`
  for scripting and quick checks without the TUI.

## Requirements

- [GitHub CLI](https://cli.github.com/) (`gh`) — used for authentication
  (`gh auth token`)
- Python 3.13+
- A [Nerd Font](https://www.nerdfonts.com/) for the state icons in the TUI

## Installation

### Nix

```bash
nix build
./result/bin/forge-triage
```

### From source

```bash
nix develop  # or set up a Python 3.13 venv with textual + httpx
pip install -e .
```

## Usage

First, make sure you're authenticated with the GitHub CLI:

```bash
gh auth login
```

### Sync notifications

```bash
forge-triage sync
# Synced: 142 new, 38 updated, 994 total
```

### Launch the TUI

```bash
forge-triage
```

### CLI commands

```bash
# List notifications sorted by priority
forge-triage ls

# Show statistics
forge-triage stats
# Total: 994
#
# By priority:
#   🔴 blocking: 108
#   🟡 action: 66
#   ⚪ fyi: 820

# Mark a notification as done
forge-triage done owner/repo#123

# Dismiss all notifications with a given reason
forge-triage done --reason subscribed

# Run arbitrary SQL against the local database
forge-triage sql "SELECT count(*) FROM notifications WHERE priority_tier = 'blocking'"
```

## Keybindings

### Main list

| Key        | Action                        |
|------------|-------------------------------|
| `j` / `↓`  | Move down                     |
| `k` / `↑`  | Move up                       |
| `Enter`    | Open detail view              |
| `d`        | Mark done                     |
| `o`        | Open in browser               |
| `/`        | Filter by text                |
| `Escape`   | Clear filter                  |
| `:`        | Open command palette (PR only)|
| `r`        | Refresh list                  |
| `?`        | Help                          |
| `q`        | Quit                          |

### Detail view

| Key             | Action                        |
|-----------------|-------------------------------|
| `j` / `k`       | Scroll down / up              |
| `g` / `Home`    | Jump to top                   |
| `G` / `End`     | Jump to bottom                |
| `Ctrl+d`        | Scroll half-page down         |
| `Ctrl+u`        | Scroll half-page up           |
| `1` / `2`       | Switch to Conversation / Files Changed tab |
| `Tab`           | Next tab                      |
| `Shift+Tab` / `h` / `l` | Prev / next tab      |
| `/`             | Search in current tab         |
| `n` / `N`       | Next / previous search match  |
| `:`             | Open command palette          |
| `r`             | Refresh from GitHub API       |
| `o`             | Open in browser               |
| `d`             | Mark done and go back         |
| `q` / `Escape`  | Go back                       |
| `?`             | Help                          |

## User-defined commands

Create `~/.config/forge-triage/commands.toml` to add commands to the `:` palette:

```toml
[[commands]]
name = "Checkout PR"
args = ["gh", "pr", "checkout", "{pr_number}"]
mode = "foreground"

[[commands]]
name = "Open CI"
args = ["open", "https://github.com/{repo}/actions"]
mode = "background"
```

**Fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `name` | ✓ | Label shown in the palette |
| `args` | ✓ | Command and arguments as a list (no shell interpolation) |
| `mode` | ✓ | `"foreground"` suspends the TUI; `"background"` fires and forgets |
| `cwd`  | | Working directory (supports template vars and `~`/`$HOME`) |
| `env`  | | Extra environment variables added to the command's environment |

**Template variables** available in `args`, `cwd`, and `env` values:

| Variable | Available | Description |
|----------|-----------|-------------|
| `{repo}` | Always | `owner/name` e.g. `NixOS/nixpkgs` |
| `{repo_owner}` | Always | e.g. `NixOS` |
| `{repo_name}` | Always | e.g. `nixpkgs` |
| `{pr_number}` | After PR details load | PR number as a string |
| `{branch}` | After PR details load | Head branch name |

**Example — workmux + nixpkgs-review:**

```toml
[[commands]]
name = "Checkout PR (workmux)"
args = ["workmux", "add", "--pr", "{pr_number}", "--open-if-exists"]
cwd = "$HOME/git/{repo_name}"
mode = "foreground"

[commands.env]
GH_REPO = "{repo}"

[[commands]]
name = "nixpkgs-review PR"
args = ["tmux", "new-window", "nixpkgs-review pr {pr_number}; $SHELL"]
cwd = "$HOME/git/{repo_name}"
mode = "background"
```

## Development

```bash
nix develop

# Run tests
pytest

# Type checking
mypy src/ tests/

# Lint + format
ruff check src/ tests/
ruff format src/ tests/
```
