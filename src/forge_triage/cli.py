"""CLI entry point and subcommand definitions."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from forge_triage.db import (
    Notification,
    SqlWriteBlockedError,
    delete_notification,
    execute_sql,
    get_notification_ids_by_reason,
    get_notification_ids_by_repo_title,
    get_notification_stats,
    list_notifications,
    open_db,
)
from forge_triage.github import get_github_token, mark_as_read
from forge_triage.sync import DEFAULT_MAX_NOTIFICATIONS, sync

COL_TITLE_MAX = 48
COL_REPO_MAX = 28


def _print_progress(current: int, total: int) -> None:
    """Print a progress bar to stderr."""
    width = 40
    filled = int(width * current / total) if total > 0 else 0
    bar = "█" * filled + "░" * (width - filled)
    print(f"\r  {bar} {current}/{total}", end="", file=sys.stderr, flush=True)
    if current == total:
        print(file=sys.stderr)


def _cmd_sync(args: argparse.Namespace) -> None:
    """Run sync: fetch notifications from GitHub."""
    token = get_github_token()
    conn = open_db()
    max_n: int = args.max
    try:
        result = asyncio.run(
            sync(conn, token, max_notifications=max_n, on_progress=_print_progress)
        )
        print(f"Synced: {result.new} new, {result.updated} updated, {result.total} total")
    finally:
        conn.close()


def _cmd_ls(args: argparse.Namespace) -> None:
    """List notifications sorted by priority."""
    conn = open_db()
    try:
        rows = list_notifications(conn)
        if not rows:
            print("Inbox is empty. Run `forge-triage sync` to fetch notifications.")
            return
        if args.json:
            print(json.dumps([r.to_dict() for r in rows], indent=2))
        else:
            _print_notification_table(rows)
    finally:
        conn.close()


def _tier_indicator(tier: str) -> str:
    indicators = {"blocking": "🔴", "action": "🟡", "fyi": "⚪"}
    return indicators.get(tier, "⚪")


def _print_notification_table(rows: list[Notification]) -> None:
    """Print notifications as a formatted table."""
    # Header
    print(f"{'':2} {'Repo':<30} {'Title':<50} {'Reason':<20}")
    print("─" * 104)
    for row in rows:
        indicator = _tier_indicator(row.priority_tier)
        repo = f"{row.repo_owner}/{row.repo_name}"
        title = row.subject_title
        if len(title) > COL_TITLE_MAX:
            title = title[: COL_TITLE_MAX - 1] + "…"
        if len(repo) > COL_REPO_MAX:
            repo = repo[: COL_REPO_MAX - 1] + "…"
        print(f"{indicator} {repo:<30} {title:<50} {row.reason:<20}")


def _cmd_stats(_args: argparse.Namespace) -> None:
    """Show notification statistics."""
    conn = open_db()
    try:
        stats = get_notification_stats(conn)
        if stats.total == 0:
            print("No notifications.")
            return

        print(f"Total: {stats.total}")
        print()

        # Per tier
        print("By priority:")
        for s in stats.by_tier:
            print(f"  {_tier_indicator(s.label)} {s.label}: {s.count}")
        print()

        # Per repo
        print("By repo:")
        for s in stats.by_repo:
            print(f"  {s.label}: {s.count}")
        print()

        # Per reason
        print("By reason:")
        for s in stats.by_reason:
            print(f"  {s.label}: {s.count}")
    finally:
        conn.close()


def _cmd_sql(args: argparse.Namespace) -> None:
    """Execute a raw SQL query against the database."""
    conn = open_db()
    try:
        result = execute_sql(conn, args.query, allow_write=args.write)
    except SqlWriteBlockedError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    else:
        if result.columns is None:
            print("OK")
        elif args.json:
            print(
                json.dumps(
                    [dict(zip(result.columns, row, strict=True)) for row in result.rows],
                    indent=2,
                )
            )
        else:
            print("\t".join(result.columns))
            for row in result.rows:
                print("\t".join(str(v) for v in row))
    finally:
        conn.close()


def _cmd_done(args: argparse.Namespace) -> None:
    """Mark notifications as done."""
    token = get_github_token()
    conn = open_db()
    try:
        if args.reason:
            nids = get_notification_ids_by_reason(conn, args.reason)
        elif args.ref:
            # Parse owner/repo#number format
            ref: str = args.ref
            if "#" in ref:
                repo_part, _number = ref.rsplit("#", 1)
                nids = get_notification_ids_by_repo_title(conn, repo_part, f"%#{_number}%")
            else:
                print(f"Invalid ref format: {ref}. Expected owner/repo#number", file=sys.stderr)
                sys.exit(1)
        else:
            print("Specify a ref (owner/repo#number) or --reason", file=sys.stderr)
            sys.exit(1)

        if not nids:
            print("No matching notifications found.")
            return

        count = 0
        for nid in nids:
            asyncio.run(mark_as_read(token, nid))
            delete_notification(conn, nid)
            count += 1
        print(f"Done: {count} notification(s) dismissed.")
    finally:
        conn.close()


def _launch_tui() -> None:
    """Launch the Textual TUI with a backend worker.

    Imports are deferred to avoid loading Textual/backend for CLI-only commands.
    """
    from forge_triage.backend import backend_worker  # noqa: PLC0415
    from forge_triage.messages import (  # noqa: PLC0415, TC001
        ErrorResult,
        FetchCommentsRequest,
        FetchCommentsResult,
        MarkDoneRequest,
        MarkDoneResult,
        PreLoadCommentsRequest,
        PreLoadComplete,
    )
    from forge_triage.tui.app import TriageApp  # noqa: PLC0415

    conn = open_db()
    token = get_github_token()

    request_queue: asyncio.Queue[
        MarkDoneRequest | FetchCommentsRequest | PreLoadCommentsRequest
    ] = asyncio.Queue()
    response_queue: asyncio.Queue[
        MarkDoneResult | FetchCommentsResult | PreLoadComplete | ErrorResult
    ] = asyncio.Queue()

    app = TriageApp(
        conn=conn,
        request_queue=request_queue,
        response_queue=response_queue,
    )

    async def _run() -> None:
        worker = asyncio.create_task(backend_worker(request_queue, response_queue, conn, token))
        try:
            await app.run_async()
        finally:
            worker.cancel()

    asyncio.run(_run())


def main(argv: list[str] | None = None) -> None:
    """Parse arguments and dispatch to the appropriate subcommand."""
    parser = argparse.ArgumentParser(
        prog="forge-triage",
        description="Fast TUI for triaging GitHub notifications",
    )
    subparsers = parser.add_subparsers(dest="command")

    # sync
    sync_parser = subparsers.add_parser("sync", help="Fetch notifications from GitHub")
    sync_parser.add_argument("-v", "--verbose", action="store_true")
    sync_parser.add_argument(
        "--max",
        type=int,
        default=DEFAULT_MAX_NOTIFICATIONS,
        help=f"Maximum notifications to process (default: {DEFAULT_MAX_NOTIFICATIONS})",
    )

    # ls
    ls_parser = subparsers.add_parser("ls", help="List notifications")
    ls_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # stats
    subparsers.add_parser("stats", help="Show notification statistics")

    # sql
    sql_parser = subparsers.add_parser("sql", help="Execute raw SQL query")
    sql_parser.add_argument("query", help="SQL query to execute")
    sql_parser.add_argument("--json", action="store_true", help="Output as JSON")
    sql_parser.add_argument("--write", action="store_true", help="Allow write operations")

    # done
    done_parser = subparsers.add_parser("done", help="Mark notifications as done")
    done_parser.add_argument("ref", nargs="?", help="Notification ref (owner/repo#number)")
    done_parser.add_argument("--reason", help="Dismiss all with this reason")

    args = parser.parse_args(argv)

    if args.command is None:
        _launch_tui()
        return

    dispatch = {
        "sync": _cmd_sync,
        "ls": _cmd_ls,
        "stats": _cmd_stats,
        "sql": _cmd_sql,
        "done": _cmd_done,
    }
    dispatch[args.command](args)
