"""Request/response message types for TUI ↔ backend communication."""

from __future__ import annotations

from dataclasses import dataclass, field

# === Requests (TUI → Backend) ===


@dataclass(frozen=True)
class MarkDoneRequest:
    """Ask the backend to mark notifications as read on GitHub and delete locally."""

    notification_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FetchCommentsRequest:
    """Ask the backend to fetch comments for a single notification."""

    notification_id: str


@dataclass(frozen=True)
class PreLoadCommentsRequest:
    """Ask the backend to pre-load comments for top N notifications."""

    top_n: int = 20


@dataclass(frozen=True)
class FetchPRDetailRequest:
    """Ask the backend to fetch full PR data (metadata, reviews, files)."""

    notification_id: str


@dataclass(frozen=True)
class PostReviewCommentRequest:
    """Ask the backend to post a reply to a review thread."""

    notification_id: str
    comment_id: int
    body: str


@dataclass(frozen=True)
class SubmitReviewRequest:
    """Ask the backend to submit a PR review (approve/request changes)."""

    notification_id: str
    event: str  # "APPROVE" or "REQUEST_CHANGES"
    body: str = ""


@dataclass(frozen=True)
class ResolveThreadRequest:
    """Ask the backend to resolve or unresolve a review thread."""

    notification_id: str
    thread_node_id: str
    resolve: bool = True


type Request = (
    MarkDoneRequest
    | FetchCommentsRequest
    | PreLoadCommentsRequest
    | FetchPRDetailRequest
    | PostReviewCommentRequest
    | SubmitReviewRequest
    | ResolveThreadRequest
)


# === Responses (Backend → TUI) ===


@dataclass(frozen=True)
class MarkDoneResult:
    """Report which notifications were marked done (or errors)."""

    notification_ids: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FetchCommentsResult:
    """Report fetched comments for a notification."""

    notification_id: str
    comment_count: int


@dataclass(frozen=True)
class PreLoadComplete:
    """Report which notifications had comments pre-loaded."""

    loaded_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ErrorResult:
    """Report an error processing a request."""

    request_type: str
    error: str


@dataclass(frozen=True)
class FetchPRDetailResult:
    """Report that PR detail data was fetched (or failed)."""

    notification_id: str = ""
    success: bool = True
    error: str = ""


@dataclass(frozen=True)
class PostReviewCommentResult:
    """Report that a review reply was posted (or failed)."""

    notification_id: str = ""
    success: bool = True
    error: str = ""


@dataclass(frozen=True)
class SubmitReviewResult:
    """Report that a review was submitted (or failed)."""

    notification_id: str = ""
    success: bool = True
    error: str = ""


@dataclass(frozen=True)
class ResolveThreadResult:
    """Report that a thread was resolved/unresolved (or failed)."""

    notification_id: str = ""
    success: bool = True
    error: str = ""


type Response = (
    MarkDoneResult
    | FetchCommentsResult
    | PreLoadComplete
    | ErrorResult
    | FetchPRDetailResult
    | PostReviewCommentResult
    | SubmitReviewResult
    | ResolveThreadResult
)
