#!/usr/bin/env python3
"""Create and operate a host-neutral collaboration queue JSON artifact."""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.errors import dumps_json, error_payload  # noqa: E402
from collab.queue import (  # noqa: E402
    QueueError,
    complete_lease,
    dumps_queue_json,
    fail_lease,
    lease_next,
    load_queue,
    queue_from_plan,
    requeue_lease,
    save_queue,
    summarize_queue,
)
from collab.replay import ReplayError, load_plan  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="Create a queue from a collab plan.")
    create.add_argument("--plan", required=True, type=Path)
    create.add_argument("--queue", required=True, type=Path)
    create.add_argument("--max-attempts", type=int, default=3)
    create.add_argument("--label", action="append", default=[], help="dispatch_id=label[,label] assignment; repeatable.")
    create.add_argument("--json", action="store_true")

    lease = sub.add_parser("lease", help="Lease the next queued item for a worker.")
    lease.add_argument("--queue", required=True, type=Path)
    lease.add_argument("--worker-id", required=True)
    lease.add_argument("--label", action="append", default=[], help="Required label; repeatable.")
    lease.add_argument("--max-concurrent", type=int, default=1)
    lease.add_argument("--now")
    lease.add_argument("--json", action="store_true")

    for name, help_text in (("requeue", "Requeue a leased item."), ("complete", "Mark a lease done."), ("fail", "Mark a lease error.")):
        cmd = sub.add_parser(name, help=help_text)
        cmd.add_argument("--queue", required=True, type=Path)
        cmd.add_argument("--lease-id", required=True)
        cmd.add_argument("--reason")
        cmd.add_argument("--report")
        cmd.add_argument("--json", action="store_true")

    show = sub.add_parser("show", help="Show queue summary or full queue.")
    show.add_argument("--queue", required=True, type=Path)
    show.add_argument("--full", action="store_true")
    show.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = _run(args)
    except (QueueError, ReplayError) as exc:
        if getattr(args, "json", False):
            print(dumps_json(error_payload("collab_queue_error", exc)), end="")
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if getattr(args, "json", False):
        print(dumps_json(payload), end="")
    elif payload["kind"] == "collab_queue":
        print(dumps_queue_json(payload["queue"]), end="")
    else:
        summary = payload.get("summary", payload)
        print(f"collab queue: plan={summary.get('plan_id')} items={summary.get('item_count')} all_done={summary.get('all_done')}")
    return 0


def _run(args: argparse.Namespace) -> dict:
    if args.command == "create":
        plan = load_plan(args.plan)
        queue = queue_from_plan(plan, labels_by_dispatch=_parse_label_assignments(args.label), max_attempts=args.max_attempts)
        save_queue(queue, args.queue)
        return {"kind": "collab_queue_summary", "queue_path": str(args.queue), "summary": summarize_queue(queue)}

    queue = load_queue(args.queue)
    if args.command == "lease":
        queue, item = lease_next(
            queue,
            worker_id=args.worker_id,
            labels=args.label,
            max_concurrent=args.max_concurrent,
            now=args.now,
        )
        save_queue(queue, args.queue)
        return {"kind": "collab_queue_lease", "queue_path": str(args.queue), "item": item.to_dict(), "summary": summarize_queue(queue)}
    if args.command == "requeue":
        queue = requeue_lease(queue, args.lease_id, reason=args.reason or args.report)
        save_queue(queue, args.queue)
        return {"kind": "collab_queue_summary", "queue_path": str(args.queue), "summary": summarize_queue(queue)}
    if args.command == "complete":
        queue = complete_lease(queue, args.lease_id, report=args.report or args.reason)
        save_queue(queue, args.queue)
        return {"kind": "collab_queue_summary", "queue_path": str(args.queue), "summary": summarize_queue(queue)}
    if args.command == "fail":
        queue = fail_lease(queue, args.lease_id, reason=args.reason or args.report)
        save_queue(queue, args.queue)
        return {"kind": "collab_queue_summary", "queue_path": str(args.queue), "summary": summarize_queue(queue)}
    if args.command == "show":
        if args.full:
            return {"kind": "collab_queue", "queue_path": str(args.queue), "queue": queue.to_dict()}
        return {"kind": "collab_queue_summary", "queue_path": str(args.queue), "summary": summarize_queue(queue)}
    raise QueueError(f"unknown command: {args.command}")


def _parse_label_assignments(values: list[str]) -> dict[str, list[str]]:
    assignments: dict[str, list[str]] = {}
    for value in values:
        if "=" not in value:
            raise QueueError("--label for create must use dispatch_id=label[,label]")
        dispatch_id, labels_text = value.split("=", 1)
        dispatch_id = dispatch_id.strip()
        if not dispatch_id:
            raise QueueError("label dispatch_id is required")
        assignments[dispatch_id] = [part.strip() for part in labels_text.split(",") if part.strip()]
    return assignments


if __name__ == "__main__":
    raise SystemExit(main())
