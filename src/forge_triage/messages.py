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


type Request = MarkDoneRequest | FetchCommentsRequest | PreLoadCommentsRequest


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


type Response = MarkDoneResult | FetchCommentsResult | PreLoadComplete | ErrorResult
