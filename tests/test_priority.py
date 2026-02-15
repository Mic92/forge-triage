"""Integration tests for the priority engine."""

from __future__ import annotations

from forge_triage.priority import compute_priority


def test_priority_ordering() -> None:
    """Verify the full priority ordering across all tiers and edge cases."""
    cases = [
        # (reason, ci_status) → expected (score, tier)
        ("review_requested", "success"),  # highest: blocking someone, CI green
        ("review_requested", "failure"),  # blocking but CI red
        ("review_requested", None),  # blocking, unknown CI
        ("mention", None),  # action needed
        ("assign", None),  # action needed
        ("team_mention", None),  # FYI
        ("subscribed", None),  # lowest FYI
        ("some_future_reason", None),  # unknown reason → FYI fallback
        ("subscribed", "failure"),  # CI status irrelevant for non-review
    ]
    scores = [compute_priority(r, ci) for r, ci in cases]

    # Verify monotonically non-increasing scores
    for i in range(len(scores) - 1):
        assert scores[i][0] >= scores[i + 1][0], (
            f"Expected {scores[i]} >= {scores[i + 1]} for cases[{i}] vs cases[{i + 1}]"
        )

    # Verify specific tier assignments
    assert scores[0] == (1000, "blocking")
    assert scores[1] == (800, "blocking")
    assert scores[3] == (600, "action")
    assert scores[5] == (200, "fyi")
    assert scores[6] == (100, "fyi")
    assert scores[7] == (100, "fyi")  # unknown reason
    assert scores[8] == (100, "fyi")  # CI status doesn't affect non-review
