"""GitHub API client — notifications, comments, CI status, triage actions."""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

API_BASE = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"
GRAPHQL_BATCH_SIZE = 100  # nodes per query (conservative vs GitHub's ~500 limit)
REQUEST_TIMEOUT = 60.0  # seconds — GraphQL batch queries can be slow

_SUBJECT_URL_RE = re.compile(
    r"https://api\.github\.com/repos/(?P<owner>[^/]+)/(?P<repo>[^/]+)"
    r"/(?P<kind>pulls|issues)/(?P<number>\d+)$"
)


@dataclass(frozen=True)
class ParsedSubject:
    """A parsed GitHub subject URL."""

    owner: str
    repo: str
    number: int
    kind: str  # "pull_request" or "issue"


def parse_subject_url(url: str | None) -> ParsedSubject | None:
    """Extract owner, repo, number, and kind from a GitHub API subject URL.

    Returns None for null URLs or URLs that don't match the expected pattern.
    """
    if url is None:
        return None
    m = _SUBJECT_URL_RE.match(url)
    if m is None:
        return None
    kind = "pull_request" if m.group("kind") == "pulls" else "issue"
    return ParsedSubject(
        owner=m.group("owner"),
        repo=m.group("repo"),
        number=int(m.group("number")),
        kind=kind,
    )


RATE_LIMIT_WARNING_THRESHOLD = 100


SubjectDetails = tuple[str | None, str | None]
"""(subject_state, ci_status) for a notification."""


_PR_FRAGMENT = """\
fragment PrDetails on PullRequest {
  state
  merged
  commits(last: 1) { nodes { commit { statusCheckRollup { state } } } }
}"""

_ISSUE_FRAGMENT = """\
fragment IssueDetails on Issue {
  state
}"""


_GRAPHQL_IDENTIFIER_RE = re.compile(r"^[a-zA-Z0-9._-]+$")


def _validate_graphql_identifier(s: str) -> str:
    """Validate that a string is safe to interpolate into a GraphQL query.

    Raises ValueError if the string contains characters outside [a-zA-Z0-9._-].
    """
    if not _GRAPHQL_IDENTIFIER_RE.match(s):
        msg = f"Invalid GraphQL identifier: {s!r}"
        raise ValueError(msg)
    return s


def _build_subject_details_query(
    subjects: dict[str, ParsedSubject],
) -> tuple[str, dict[str, str]]:
    """Build a GraphQL query to fetch details for multiple subjects.

    Groups subjects by (owner, repo) and uses fragments to avoid repeating
    field selections per node.
    Returns (query_string, alias_to_notification_id mapping).
    """
    # Group by (owner, repo)
    repos: dict[tuple[str, str], list[tuple[str, ParsedSubject]]] = {}
    for nid, parsed in subjects.items():
        key = (parsed.owner, parsed.repo)
        repos.setdefault(key, []).append((nid, parsed))

    alias_map: dict[str, str] = {}  # graphql alias → notification_id
    repo_fragments: list[str] = []
    has_pr = False
    has_issue = False

    for repo_idx, ((owner, repo), items) in enumerate(repos.items()):
        _validate_graphql_identifier(owner)
        _validate_graphql_identifier(repo)

        node_fragments: list[str] = []
        for nid, parsed in items:
            if parsed.kind == "pull_request":
                alias = f"pr_{nid}"
                node_fragments.append(
                    f"    {alias}: pullRequest(number: {parsed.number}) {{ ...PrDetails }}"
                )
                has_pr = True
            else:
                alias = f"issue_{nid}"
                node_fragments.append(
                    f"    {alias}: issue(number: {parsed.number}) {{ ...IssueDetails }}"
                )
                has_issue = True
            alias_map[alias] = nid

        repo_alias = f"r{repo_idx}"
        repo_fragments.append(
            f'  {repo_alias}: repository(owner: "{owner}", name: "{repo}") {{\n'
            + "\n".join(node_fragments)
            + "\n  }"
        )

    parts: list[str] = []
    if has_pr:
        parts.append(_PR_FRAGMENT)
    if has_issue:
        parts.append(_ISSUE_FRAGMENT)
    parts.append("query {\n" + "\n".join(repo_fragments) + "\n}")

    return "\n".join(parts), alias_map


def _parse_pr_state(node_data: dict[str, Any]) -> SubjectDetails:
    """Extract (subject_state, ci_status) from a PR GraphQL node."""
    state = node_data.get("state", "").upper()
    merged = node_data.get("merged", False)
    if merged:
        subject_state = "merged"
    elif state == "OPEN":
        subject_state = "open"
    elif state == "CLOSED":
        subject_state = "closed"
    else:
        subject_state = None

    ci_status: str | None = None
    nodes = node_data.get("commits", {}).get("nodes", [])
    if nodes:
        rollup = nodes[0].get("commit", {}).get("statusCheckRollup")
        if rollup is not None:
            raw_ci = rollup.get("state", "").lower()
            if raw_ci in ("success", "failure", "pending", "error"):
                ci_status = raw_ci

    return (subject_state, ci_status)


def _parse_issue_state(node_data: dict[str, Any]) -> SubjectDetails:
    """Extract (subject_state, ci_status) from an Issue GraphQL node."""
    state = node_data.get("state", "").upper()
    if state == "OPEN":
        return ("open", None)
    if state == "CLOSED":
        return ("closed", None)
    return (None, None)


def _parse_graphql_response(
    data: dict[str, Any],
    alias_map: dict[str, str],
) -> dict[str, SubjectDetails]:
    """Parse a GraphQL response into notification_id → (subject_state, ci_status)."""
    results: dict[str, SubjectDetails] = {}

    for repo_data in data.values():
        if repo_data is None:
            continue
        for alias, node_data in repo_data.items():
            nid = alias_map.get(alias)
            if nid is None:
                continue
            if node_data is None:
                results[nid] = (None, None)
            elif alias.startswith("pr_"):
                results[nid] = _parse_pr_state(node_data)
            elif alias.startswith("issue_"):
                results[nid] = _parse_issue_state(node_data)

    return results


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
    async with httpx.AsyncClient(headers=headers, timeout=REQUEST_TIMEOUT) as client:
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
    async with httpx.AsyncClient(headers=headers, timeout=REQUEST_TIMEOUT) as client:
        next_url: str | None = comments_url
        while next_url:
            response = await client.get(next_url)
            _check_rate_limit(response)
            response.raise_for_status()
            comments.extend(response.json())
            link = response.headers.get("Link", "")
            next_url = _parse_next_link(link)
    return comments


async def fetch_subject_details(
    token: str,
    notifications: list[dict[str, Any]],
) -> dict[str, SubjectDetails]:
    """Batch-fetch subject state and CI status for notifications via GraphQL.

    Returns a dict mapping notification_id → (subject_state, ci_status).
    Notifications with unparseable URLs are excluded (callers should default to (None, None)).
    """
    # Parse URLs and filter to fetchable subjects
    subjects: dict[str, ParsedSubject] = {}
    for notif in notifications:
        url: str | None = notif["subject"]["url"]
        parsed = parse_subject_url(url)
        if parsed is not None:
            subjects[notif["id"]] = parsed

    if not subjects:
        return {}

    results: dict[str, SubjectDetails] = {}
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}

    # Batch into chunks
    subject_items = list(subjects.items())
    async with httpx.AsyncClient(headers=headers, timeout=REQUEST_TIMEOUT) as client:
        for start in range(0, len(subject_items), GRAPHQL_BATCH_SIZE):
            batch = dict(subject_items[start : start + GRAPHQL_BATCH_SIZE])
            query, alias_map = _build_subject_details_query(batch)

            response = await client.post(GRAPHQL_URL, json={"query": query})
            response.raise_for_status()
            body = response.json()

            errors = body.get("errors")
            if errors:
                logger.warning("GraphQL errors: %s", errors)

            data = body.get("data")
            if data is not None:
                results.update(_parse_graphql_response(data, alias_map))

            # Mark any unfetched notifications (errors / missing) as (None, None)
            for nid in alias_map.values():
                if nid not in results:
                    results[nid] = (None, None)

    return results


async def mark_as_read(token: str, thread_id: str) -> None:
    """Mark a notification thread as read on GitHub."""
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    async with httpx.AsyncClient(headers=headers, timeout=REQUEST_TIMEOUT) as client:
        response = await client.patch(f"{API_BASE}/notifications/threads/{thread_id}")
        _check_rate_limit(response)
        response.raise_for_status()
