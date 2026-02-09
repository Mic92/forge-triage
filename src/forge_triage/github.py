"""GitHub API client — notifications, comments, CI status, triage actions."""

from __future__ import annotations

import logging
import re
import subprocess
from typing import Any

import httpx

logger = logging.getLogger(__name__)

API_BASE = "https://api.github.com"
RATE_LIMIT_WARNING_THRESHOLD = 100


class AuthError(Exception):
    """Raised when GitHub authentication fails."""


class RateLimitError(Exception):
    """Raised when GitHub API rate limit is exceeded."""


def get_github_token() -> str:
    """Obtain a GitHub token via `gh auth token`."""
    result = subprocess.run(
        ["gh", "auth", "token"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        msg = "gh CLI not authenticated. Run: gh auth login"
        raise AuthError(msg)
    token = result.stdout.strip()
    if not token:
        msg = "gh auth token returned empty output"
        raise AuthError(msg)
    return token


def _check_rate_limit(response: httpx.Response) -> None:
    """Log a warning if rate limit is low, raise if exceeded."""
    remaining = response.headers.get("X-RateLimit-Remaining")
    if remaining is not None:
        remaining_int = int(remaining)
        if remaining_int < RATE_LIMIT_WARNING_THRESHOLD:
            logger.warning("GitHub API rate limit low: %d remaining", remaining_int)
    if response.status_code == httpx.codes.FORBIDDEN and "rate limit" in response.text.lower():
        msg = "GitHub API rate limit exceeded"
        raise RateLimitError(msg)


def _parse_next_link(link_header: str) -> str | None:
    """Extract the 'next' URL from a GitHub Link header."""
    match = re.search(r'<([^>]+)>;\s*rel="next"', link_header)
    return match.group(1) if match else None


async def fetch_notifications(
    token: str,
    since: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch all notification pages from the GitHub API."""
    notifications: list[dict[str, Any]] = []
    params: dict[str, str] = {}
    if since:
        params["since"] = since

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    async with httpx.AsyncClient(headers=headers) as client:
        next_url: str | None = f"{API_BASE}/notifications"
        is_first = True
        while next_url:
            # Only pass params on the first request; pagination URLs have params baked in.
            # Passing even an empty params= to httpx strips existing query strings.
            response = await client.get(next_url, params=params if is_first else None)
            is_first = False
            _check_rate_limit(response)
            response.raise_for_status()
            notifications.extend(response.json())

            link = response.headers.get("Link", "")
            next_url = _parse_next_link(link)

    return notifications


async def fetch_comments(
    token: str,
    comments_url: str,
) -> list[dict[str, Any]]:
    """Fetch comments from a GitHub issue/PR comments URL."""
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    comments: list[dict[str, Any]] = []
    async with httpx.AsyncClient(headers=headers) as client:
        next_url: str | None = comments_url
        while next_url:
            response = await client.get(next_url)
            _check_rate_limit(response)
            response.raise_for_status()
            comments.extend(response.json())
            link = response.headers.get("Link", "")
            next_url = _parse_next_link(link)
    return comments


async def fetch_ci_status(
    token: str,
    repo_full_name: str,
    pr_url: str,
) -> str | None:
    """Fetch combined CI status for a PR. Returns 'success', 'failure', 'pending', or None."""
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    async with httpx.AsyncClient(headers=headers) as client:
        # First get the PR to find head SHA
        response = await client.get(pr_url)
        _check_rate_limit(response)
        response.raise_for_status()
        pr_data: dict[str, Any] = response.json()
        head_sha: str = pr_data["head"]["sha"]

        # Then get combined status
        status_url = f"{API_BASE}/repos/{repo_full_name}/commits/{head_sha}/status"
        response = await client.get(status_url)
        _check_rate_limit(response)
        response.raise_for_status()
        status_data: dict[str, Any] = response.json()
        state: str = status_data["state"]
        return state if state != "pending" or status_data["total_count"] > 0 else None


async def mark_as_read(token: str, thread_id: str) -> None:
    """Mark a notification thread as read on GitHub."""
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    async with httpx.AsyncClient(headers=headers) as client:
        response = await client.patch(f"{API_BASE}/notifications/threads/{thread_id}")
        _check_rate_limit(response)
        response.raise_for_status()
