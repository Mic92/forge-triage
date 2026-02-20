"""PR command runner: template substitution and subprocess execution."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import App, SuspendNotSupported

if TYPE_CHECKING:
    from forge_triage.db import Notification
    from forge_triage.pr_db import PRDetails


def build_template_vars(notif: Notification, pr_details: PRDetails | None) -> dict[str, str]:
    """Build template variable dict from notification and optional PR details.

    Always includes {repo}, {repo_owner}, {repo_name}. Includes {pr_number}
    and {branch} only when PR details are available (and head_ref is non-None
    for {branch}).
    """
    template_vars: dict[str, str] = {
        "repo": f"{notif.repo_owner}/{notif.repo_name}",
        "repo_owner": notif.repo_owner,
        "repo_name": notif.repo_name,
    }
    if pr_details is not None:
        template_vars["pr_number"] = str(pr_details.pr_number)
        if pr_details.head_ref is not None:
            template_vars["branch"] = pr_details.head_ref
    return template_vars


def resolve_cwd(cwd: str | None, template_vars: dict[str, str]) -> Path | None:
    """Resolve a cwd template string to an absolute Path, or None if not set."""
    if cwd is None:
        return None
    resolved = cwd.format_map(template_vars)
    return Path(os.path.expandvars(resolved)).expanduser()


def resolve_env(env: dict[str, str] | None, template_vars: dict[str, str]) -> dict[str, str] | None:
    """Resolve env var values via template substitution, merged on top of the current env.

    Returns None if no extra env vars are configured (subprocess inherits env as-is).
    """
    if not env:
        return None
    merged = dict(os.environ)
    for key, value in env.items():
        merged[key] = value.format_map(template_vars)
    return merged


def run_foreground(
    app: App[None],
    args: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> None:
    """Suspend the TUI, run a subprocess in the foreground, then restore."""
    try:
        with app.suspend():
            subprocess.run(args, check=False, cwd=cwd, env=env)  # noqa: S603
    except SuspendNotSupported:
        app.notify("Foreground commands not supported in this environment", severity="error")


def run_background(
    args: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> None:
    """Fire-and-forget: launch a subprocess detached from the terminal."""
    subprocess.Popen(args, start_new_session=True, cwd=cwd, env=env)  # noqa: S603
