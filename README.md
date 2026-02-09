# forge-triage

A fast terminal UI for triaging GitHub notifications. Prioritizes what
needs your attention, lets you triage with vim-style keybindings, and
keeps everything in a local SQLite database for instant access.

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

 q Quit  ? Help  d Done  D Bulk Done  o Open  / Filter  r Refresh
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
- **Vim keybindings** — `j`/`k` navigation, `d` to mark done, `o` to
  open in browser, `/` to filter.
- **Batch operations** — Select with `x`, select all with `*`, bulk
  dismiss with `D`.
- **Comment pre-loading** — Top priority notifications have their
  comments fetched automatically during sync.
- **GraphQL batch fetching** — PR/issue state and CI status are fetched
  in bulk via the GitHub GraphQL API to minimise API calls.
- **Local SQLite database** — All data is stored locally for instant startup and offline browsing.
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

| Key       | Action                 |
|-----------|------------------------|
| `j` / `↓` | Move down             |
| `k` / `↑` | Move up               |
| `d`       | Mark done (single)     |
| `D`       | Mark done (selected)   |
| `x`       | Toggle selection       |
| `*`       | Select all visible     |
| `o`       | Open in browser        |
| `/`       | Filter by text         |
| `r`       | Refresh list           |
| `Escape`  | Clear filter           |
| `?`       | Help                   |
| `q`       | Quit                   |

## Development

```bash
nix develop

# Run tests
pytest

# Type checking
mypy

# Lint + format
ruff check .
ruff format .
```
