"""Tests for pr_command_runner: build_template_vars, resolve_cwd, resolve_env, run_foreground."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

from textual.app import SuspendNotSupported

from forge_triage.db import Notification
from forge_triage.pr_db import PRDetails
from forge_triage.tui.widgets.pr_command_runner import (
    build_template_vars,
    resolve_cwd,
    resolve_env,
    run_foreground,
)


def _make_notification() -> Notification:
    return Notification(
        notification_id="1001",
        repo_owner="NixOS",
        repo_name="nixpkgs",
        subject_type="PullRequest",
        subject_title="python313: 3.13.1 -> 3.13.2",
        subject_url="https://api.github.com/repos/NixOS/nixpkgs/pulls/12345",
        html_url="https://github.com/NixOS/nixpkgs/pull/12345",
        reason="review_requested",
        updated_at="2026-02-09T07:00:00Z",
        unread=1,
        priority_score=0,
        priority_tier="fyi",
        raw_json="{}",
        comments_loaded=0,
        last_viewed_at=None,
        ci_status=None,
        subject_state=None,
    )


def _make_pr_details(*, head_ref: str | None = "python-update") -> PRDetails:
    return PRDetails(
        notification_id="1001",
        pr_number=12345,
        author="contributor",
        body="Update python 3.13",
        labels_json="[]",
        base_ref="main",
        head_ref=head_ref,
        loaded_at="2026-02-09T08:00:00Z",
    )


def test_build_template_vars_full_pr_details() -> None:
    """Full PR details → dict with all vars including repo_owner and repo_name."""
    notif = _make_notification()
    pr = _make_pr_details()
    result = build_template_vars(notif, pr)
    assert result == {
        "repo": "NixOS/nixpkgs",
        "repo_owner": "NixOS",
        "repo_name": "nixpkgs",
        "pr_number": "12345",
        "branch": "python-update",
    }


def test_build_template_vars_no_pr_details() -> None:
    """pr_details=None → dict with only repo vars."""
    notif = _make_notification()
    result = build_template_vars(notif, None)
    assert result == {
        "repo": "NixOS/nixpkgs",
        "repo_owner": "NixOS",
        "repo_name": "nixpkgs",
    }


def test_build_template_vars_head_ref_none() -> None:
    """head_ref=None → dict omits {branch}."""
    notif = _make_notification()
    pr = _make_pr_details(head_ref=None)
    result = build_template_vars(notif, pr)
    assert result == {
        "repo": "NixOS/nixpkgs",
        "repo_owner": "NixOS",
        "repo_name": "nixpkgs",
        "pr_number": "12345",
    }
    assert "branch" not in result


def test_resolve_cwd_none() -> None:
    """cwd=None → returns None."""
    assert resolve_cwd(None, {}) is None


def test_resolve_cwd_template_substitution() -> None:
    """cwd with template vars → substituted and expanded Path."""
    result = resolve_cwd("$HOME/git/{repo_name}", {"repo_name": "nixpkgs"})
    assert result == Path.home() / "git" / "nixpkgs"


def test_run_foreground_suspend_not_supported_calls_notify() -> None:
    """SuspendNotSupported → app.notify() called with error severity."""
    app = MagicMock()
    app.suspend.side_effect = SuspendNotSupported

    run_foreground(app, ["gh", "pr", "checkout", "123"])

    app.notify.assert_called_once()
    _msg, kwargs = app.notify.call_args[0], app.notify.call_args[1]
    assert kwargs.get("severity") == "error"


def test_resolve_env_none() -> None:
    """env=None → returns None (subprocess inherits environment as-is)."""
    assert resolve_env(None, {}) is None


def test_resolve_env_substitutes_and_merges() -> None:
    """env dict → values are template-substituted and merged on top of os.environ."""
    result = resolve_env({"GH_REPO": "{repo}"}, {"repo": "NixOS/nixpkgs"})
    assert result is not None
    assert result["GH_REPO"] == "NixOS/nixpkgs"
    # Existing env vars are preserved
    assert result["HOME"] == os.environ["HOME"]
