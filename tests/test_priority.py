"""Integration tests for the priority engine."""

from __future__ import annotations

from forge_triage.priority import compute_priority


def test_priority_ordering() -> None:
    """Verify the full priority ordering across all tiers and edge cases."""
    cases = [
        # (reason, ci_status, is_own_pr) → expected (score, tier)
        ("review_requested", "success", False),  # highest: blocking someone, CI green
        ("review_requested", "failure", False),  # blocking but CI red
        ("review_requested", None, False),  # blocking, unknown CI
        ("mention", None, False),  # action needed
        ("assign", None, False),  # action needed
        ("subscribed", "failure", True),  # own PR CI fail
        ("team_mention", None, False),  # FYI
        ("subscribed", None, False),  # lowest FYI
        ("some_future_reason", None, False),  # unknown reason → FYI fallback
        ("subscribed", "failure", False),  # not own PR → no CI boost
    ]
    scores = [compute_priority(r, ci, is_own_pr=own) for r, ci, own in cases]

    # Verify monotonically non-increasing scores
    for i in range(len(scores) - 1):
        assert scores[i][0] >= scores[i + 1][0], (
            f"Expected {scores[i]} >= {scores[i + 1]} for cases[{i}] vs cases[{i + 1}]"
        )

    # Verify specific tier assignments
    assert scores[0] == (1000, "blocking")
    assert scores[1] == (800, "blocking")
    assert scores[3] == (600, "action")
    assert scores[5] == (500, "action")
    assert scores[6] == (200, "fyi")
    assert scores[7] == (100, "fyi")
    assert scores[8] == (100, "fyi")  # unknown reason
    assert scores[9] == (100, "fyi")  # not own PR, no boost
