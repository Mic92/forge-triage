"""Priority scoring engine for notifications."""

from __future__ import annotations

SCORE_REVIEW_REQUESTED_CI_PASS = 1000
SCORE_REVIEW_REQUESTED = 800
SCORE_MENTION_OR_ASSIGN = 600
SCORE_OWN_PR_CI_FAIL = 500
SCORE_TEAM_MENTION = 200
SCORE_DEFAULT = 100


def compute_priority(
    reason: str,
    ci_status: str | None,
    *,
    is_own_pr: bool,
) -> tuple[int, str]:
    """Compute (score, tier) for a notification.

    Tiers: "blocking", "action", "fyi".
    """
    if reason == "review_requested":
        if ci_status == "success":
            return (SCORE_REVIEW_REQUESTED_CI_PASS, "blocking")
        return (SCORE_REVIEW_REQUESTED, "blocking")

    if reason in ("mention", "assign"):
        return (SCORE_MENTION_OR_ASSIGN, "action")

    if is_own_pr and ci_status == "failure":
        return (SCORE_OWN_PR_CI_FAIL, "action")

    if reason == "team_mention":
        return (SCORE_TEAM_MENTION, "fyi")

    return (SCORE_DEFAULT, "fyi")
