"""GitHub API client for PR-specific data: metadata, review threads, files, mutations."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from forge_triage.github import API_BASE, GRAPHQL_URL, REQUEST_TIMEOUT, _parse_next_link

logger = logging.getLogger(__name__)


# --- GraphQL queries ---

_PR_METADATA_QUERY = """\
query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      number
      author { login }
      body
      labels(first: 50) { nodes { name } }
      baseRefName
      headRefName
    }
  }
}"""

_REVIEW_THREADS_QUERY = """\
query($owner: String!, $repo: String!, $number: Int!, $threadsCursor: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $threadsCursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          isResolved
          comments(first: 100) {
            nodes {
              id
              author { login }
              body
              path
              diffHunk
              line
              createdAt
              updatedAt
            }
          }
        }
      }
      reviews(first: 100) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          author { login }
          state
          body
          submittedAt
        }
      }
    }
  }
}"""


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}


# --- Parsers ---


def parse_pr_metadata_response(response: dict[str, Any]) -> dict[str, str | int | None]:
    """Parse a GraphQL PR metadata response into a flat dict for pr_db."""
    pr = response["data"]["repository"]["pullRequest"]
    labels = [node["name"] for node in pr.get("labels", {}).get("nodes", [])]
    author = pr.get("author")
    return {
        "pr_number": pr["number"],
        "author": author["login"] if author else "[deleted]",
        "body": pr.get("body"),
        "labels_json": json.dumps(labels),
        "base_ref": pr.get("baseRefName"),
        "head_ref": pr.get("headRefName"),
    }


def parse_review_threads_response(
    response: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool, str | None]:
    """Parse a GraphQL review threads response.

    Returns (comments, reviews, has_next_page, end_cursor).
    Comments are flattened across threads with thread_id and is_resolved attached.
    """
    pr = response["data"]["repository"]["pullRequest"]

    # Threads → flattened comments
    threads_data = pr["reviewThreads"]
    comments: list[dict[str, Any]] = []
    for thread in threads_data["nodes"]:
        thread_id = thread["id"]
        is_resolved = 1 if thread["isResolved"] else 0
        for comment in thread["comments"]["nodes"]:
            author = comment.get("author")
            comments.append(
                {
                    "comment_id": comment["id"],
                    "thread_id": thread_id,
                    "author": author["login"] if author else "[deleted]",
                    "body": comment["body"],
                    "path": comment.get("path"),
                    "diff_hunk": comment.get("diffHunk"),
                    "line": comment.get("line"),
                    "is_resolved": is_resolved,
                    "created_at": comment["createdAt"],
                    "updated_at": comment["updatedAt"],
                }
            )

    # Reviews
    reviews_data = pr["reviews"]
    reviews: list[dict[str, Any]] = []
    for review in reviews_data["nodes"]:
        author = review.get("author")
        reviews.append(
            {
                "review_id": review["id"],
                "author": author["login"] if author else "[deleted]",
                "state": review["state"],
                "body": review.get("body", ""),
                "submitted_at": review["submittedAt"],
            }
        )

    page_info = threads_data["pageInfo"]
    return comments, reviews, page_info["hasNextPage"], page_info.get("endCursor")


# --- Fetch functions ---


async def fetch_pr_metadata(
    token: str,
    owner: str,
    repo: str,
    number: int,
) -> dict[str, str | int | None]:
    """Fetch PR metadata via GraphQL. Returns a dict ready for upsert_pr_details."""
    async with httpx.AsyncClient(headers=_headers(token), timeout=REQUEST_TIMEOUT) as client:
        response = await client.post(
            GRAPHQL_URL,
            json={
                "query": _PR_METADATA_QUERY,
                "variables": {"owner": owner, "repo": repo, "number": number},
            },
        )
        response.raise_for_status()
        body = response.json()
        errors = body.get("errors")
        if errors:
            logger.warning("GraphQL errors: %s", errors)
        return parse_pr_metadata_response(body)


async def fetch_review_threads(
    token: str,
    owner: str,
    repo: str,
    number: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fetch all review threads and reviews via GraphQL with cursor pagination.

    Returns (all_comments, all_reviews).
    """
    all_comments: list[dict[str, Any]] = []
    all_reviews: list[dict[str, Any]] = []
    cursor: str | None = None

    async with httpx.AsyncClient(headers=_headers(token), timeout=REQUEST_TIMEOUT) as client:
        while True:
            variables: dict[str, Any] = {
                "owner": owner,
                "repo": repo,
                "number": number,
            }
            if cursor is not None:
                variables["threadsCursor"] = cursor

            response = await client.post(
                GRAPHQL_URL,
                json={"query": _REVIEW_THREADS_QUERY, "variables": variables},
            )
            response.raise_for_status()

            body = response.json()
            errors = body.get("errors")
            if errors:
                logger.warning("GraphQL errors: %s", errors)

            comments, reviews, has_next, cursor = parse_review_threads_response(body)
            all_comments.extend(comments)
            # Only collect reviews from the first page (they're not paginated by thread cursor)
            if not all_reviews:
                all_reviews = reviews

            if not has_next:
                break

    return all_comments, all_reviews


async def fetch_pr_files(
    token: str,
    owner: str,
    repo: str,
    number: int,
) -> list[dict[str, str | int | None]]:
    """Fetch changed files for a PR via REST with Link-header pagination."""
    files: list[dict[str, str | int | None]] = []
    async with httpx.AsyncClient(headers=_headers(token), timeout=REQUEST_TIMEOUT) as client:
        next_url: str | None = f"{API_BASE}/repos/{owner}/{repo}/pulls/{number}/files"
        while next_url:
            response = await client.get(next_url)
            response.raise_for_status()
            files.extend(
                {
                    "filename": f["filename"],
                    "status": f["status"],
                    "additions": f["additions"],
                    "deletions": f["deletions"],
                    "patch": f.get("patch"),  # None for binary files
                }
                for f in response.json()
            )
            link = response.headers.get("Link", "")
            next_url = _parse_next_link(link)
    return files


# --- Mutations ---


@dataclass(frozen=True)
class PRRef:
    """Identifies a pull request on GitHub."""

    owner: str
    repo: str
    number: int


async def post_review_reply(
    token: str,
    pr: PRRef,
    comment_id: int,
    body: str,
) -> dict[str, Any]:
    """Post a reply to a review comment. Returns the created comment."""
    url = f"{API_BASE}/repos/{pr.owner}/{pr.repo}/pulls/{pr.number}/comments/{comment_id}/replies"
    async with httpx.AsyncClient(headers=_headers(token), timeout=REQUEST_TIMEOUT) as client:
        response = await client.post(url, json={"body": body})
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result


async def submit_review(
    token: str,
    pr: PRRef,
    event: str,
    body: str = "",
) -> dict[str, Any]:
    """Submit a PR review (APPROVE, REQUEST_CHANGES, COMMENT)."""
    url = f"{API_BASE}/repos/{pr.owner}/{pr.repo}/pulls/{pr.number}/reviews"
    payload: dict[str, str] = {"event": event}
    if body:
        payload["body"] = body
    async with httpx.AsyncClient(headers=_headers(token), timeout=REQUEST_TIMEOUT) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result


async def resolve_review_thread(token: str, thread_node_id: str) -> bool:
    """Resolve a review thread via GraphQL mutation. Returns True on success."""
    mutation = """
    mutation($threadId: ID!) {
      resolveReviewThread(input: {threadId: $threadId}) {
        thread { id isResolved }
      }
    }
    """
    async with httpx.AsyncClient(headers=_headers(token), timeout=REQUEST_TIMEOUT) as client:
        response = await client.post(
            GRAPHQL_URL,
            json={"query": mutation, "variables": {"threadId": thread_node_id}},
        )
        response.raise_for_status()
        body = response.json()
        errors = body.get("errors")
        if errors:
            logger.warning("GraphQL errors: %s", errors)
            return False
        return True


async def unresolve_review_thread(token: str, thread_node_id: str) -> bool:
    """Unresolve a review thread via GraphQL mutation. Returns True on success."""
    mutation = """
    mutation($threadId: ID!) {
      unresolveReviewThread(input: {threadId: $threadId}) {
        thread { id isResolved }
      }
    }
    """
    async with httpx.AsyncClient(headers=_headers(token), timeout=REQUEST_TIMEOUT) as client:
        response = await client.post(
            GRAPHQL_URL,
            json={"query": mutation, "variables": {"threadId": thread_node_id}},
        )
        response.raise_for_status()
        body = response.json()
        errors = body.get("errors")
        if errors:
            logger.warning("GraphQL errors: %s", errors)
            return False
        return True
