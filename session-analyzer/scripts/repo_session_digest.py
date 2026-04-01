#!/usr/bin/env python3
"""Sync repo-scoped Codex conversations into a canonical local index and emit a digest.

This script is intentionally fail-closed: if any relevant top-level thread for the
requested repo/day cannot be fully recovered, it reports `INCOMPLETE` and exits
non-zero instead of pretending the digest is complete.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore[assignment]


SCHEMA_VERSION = 3

CONTROL_KINDS = {
    "<skill>": "skill_metadata",
    "[$": "skill_invocation",
    "<subagent_notification>": "subagent_notification",
    "<turn_aborted>": "turn_aborted",
}

TITLE_GENERATOR_PREFIX = (
    "You are a helpful assistant. You will be presented with a user prompt, "
    "and your job is to provide a short title"
)

THREAD_ID_RE = re.compile(r"(?:thread_id=|thread\.id=)([0-9a-f-]{36})")
TURN_ID_RE = re.compile(r"(?:turn_id=|turn\.id=)([0-9a-f-]{36})")

INDEX_SCHEMA = """
create table if not exists threads (
    thread_id text primary key,
    created_at integer not null,
    started_at text not null,
    cwd text not null,
    match_reason text not null,
    rollout_path text not null,
    transcript_path text,
    transcript_available integer not null default 0,
    first_user_message text not null default '',
    sync_source text not null,
    completeness_status text not null,
    completeness_reason text not null,
    synced_at text not null
);

create table if not exists messages (
    thread_id text not null,
    ordinal integer not null,
    turn_id text,
    role text not null,
    kind text not null,
    raw_text text not null,
    cleaned_text text not null,
    source text not null,
    primary key (thread_id, ordinal)
);
"""

MERGE_MARKERS = (
    "pr opened and merged",
    "merged into main",
    "merged commit on `main`",
    "landed on `main`",
    "merged successfully",
    "::git-create-pr",
)

PUSH_MARKERS = (
    "::git-push",
    "pushed successfully",
    "pushed on `",
    "pushed to `origin/main`",
    "committed and pushed",
)

COMMIT_MARKERS = (
    "::git-commit",
    "committed `",
    "committed and pushed",
    "committed ",
)

LOCAL_IMPLEMENTATION_MARKERS = (
    "the change is in [",
    "updated [",
    "added [",
    "removed ",
    "fixed ",
    "wired ",
    "implemented ",
)

BLOCKED_MARKERS = (
    "i need from you",
    "need from you:",
    "before setting up",
    "waiting for",
    "need a small set of concrete inputs",
)

PLAN_MARKERS = (
    "don't make changes yet",
    "dont make changes yet",
    "just think out loud",
    "make a plan",
    "turn this into a real plan",
    "[$execplan-create]",
)

INVESTIGATION_MARKERS = (
    "find the root cause",
    "dive deep",
    "inspect this run",
    "what happened here",
    "why is",
    "root cause",
)

QUESTION_MARKERS = (
    "walk me through",
    "tell me what",
    "explain ",
    "why do we",
    "what exactly does",
    "do we need",
)

NEXT_STEP_MARKERS = (
    "what's next",
    "whats next",
    "what should i work on next",
    "what do we need to do next",
)

VERIFICATION_MARKERS = (
    "did it succeed",
    "report back",
    "poll until",
    "poll, then get back to me",
    "monitor the gh actions",
    "monitor github actions",
    "monitor the github actions",
    "is everything up to date now",
    "what do we need to do next to test this",
)

EXECUTION_OWNERSHIP_MARKERS = (
    "do this for me as much as you can",
    "you have gh cli so you can do stuff",
    "commit and push and do whatever you need to",
    "help me implement these changes",
    "ok implement that plan",
)

LOW_SIGNAL_OPERATIONAL_MARKERS = (
    "pull the latest",
    "pull the latest code",
    "pull the latest changes",
    "switch to main and pull the latest",
    "switch to main and pull",
    "git pull",
)

TERMINAL_OUTCOME_STATUSES = {
    "implemented_and_merged",
    "implemented_and_pushed",
    "handover_only",
    "question_answered",
}

URGENT_MARKERS = (
    "failed",
    "failure",
    "broken",
    "blocker",
    "incident",
    "release gate",
    "release rollout",
    "rollout",
    "deploy",
    "production",
    "live",
    "regression",
    "loader_runtime",
    "no llm response",
    "stale",
    "root cause",
)


@dataclass
class InventoryThread:
    thread_id: str
    created_at: int
    updated_at: int
    started_at: str
    cwd: str
    match_reason: str
    match_confidence: str
    inventory_reasons: list[str]
    rollout_path: str
    transcript_path: str | None
    first_user_message: str


@dataclass
class RecoveredMessage:
    ordinal: int
    turn_id: str | None
    role: str
    kind: str
    raw_text: str
    cleaned_text: str
    source: str


@dataclass
class ThreadSyncResult:
    thread_id: str
    created_at: int
    updated_at: int
    started_at: str
    cwd: str
    match_reason: str
    match_confidence: str
    inventory_reasons: list[str]
    rollout_path: str
    transcript_path: str | None
    transcript_available: bool
    first_user_message: str
    sync_source: str
    completeness_status: str
    completeness_reason: str
    assistant_tail: str
    messages: list[RecoveredMessage]


@dataclass(frozen=True)
class MatchInfo:
    reason: str
    confidence: str


@dataclass(frozen=True)
class TimeWindow:
    mode: str
    label: str
    start_utc: datetime
    end_utc: datetime
    start_ts: int
    end_ts: int
    timezone: str
    target_date: str | None
    last_hours: float | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract repo-scoped top-level Codex conversations for one calendar day "
            "or rolling time window. "
            "Fails closed if any relevant thread is incomplete."
        )
    )
    parser.add_argument("--repo", required=True, help="Repo path, e.g. ~/TaskRally")
    time_group = parser.add_mutually_exclusive_group()
    time_group.add_argument(
        "--when",
        choices=["today", "yesterday"],
        help="Relative day shortcut. Defaults to `yesterday` when no other time selector is set.",
    )
    time_group.add_argument("--date", help="Absolute calendar date in YYYY-MM-DD")
    time_group.add_argument(
        "--last-hours",
        type=float,
        help="Rolling lookback window ending now, for example `--last-hours 6`.",
    )
    parser.add_argument(
        "--timezone",
        default=os.environ.get("TZ", "America/Los_Angeles"),
        help="IANA timezone used for relative dates.",
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format.",
    )
    parser.add_argument(
        "--include-git",
        action="store_true",
        help="Attach the current repo state as supplementary context.",
    )
    parser.add_argument(
        "--include-subagents",
        action="store_true",
        help="Include subagent sessions. Off by default.",
    )
    parser.add_argument(
        "--allow-basename-fallback",
        action="store_true",
        help=(
            "Allow lower-confidence cwd basename matches outside the repo/worktree "
            "boundary. Off by default."
        ),
    )
    parser.add_argument(
        "--index-path",
        help=(
            "Canonical index path. Defaults to $CODEX_HOME/sqlite/"
            "session_message_index.sqlite"
        ),
    )
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Emit a best-effort digest even when some relevant threads are incomplete.",
    )
    return parser.parse_args()


def collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def now_in_timezone(timezone_name: str) -> datetime:
    if ZoneInfo is None:
        return datetime.now(timezone.utc)
    return datetime.now(ZoneInfo(timezone_name))


def timezone_info(timezone_name: str):
    if ZoneInfo is None:
        return timezone.utc
    return ZoneInfo(timezone_name)


def date_bounds(target: date, timezone_name: str) -> tuple[datetime, datetime, int, int]:
    zone = timezone_info(timezone_name)
    start = datetime(target.year, target.month, target.day, tzinfo=zone)
    end = start + timedelta(days=1)
    start_ts = int(start.timestamp())
    end_ts = int(end.timestamp())
    start_utc = datetime.fromtimestamp(start_ts, timezone.utc)
    end_utc = datetime.fromtimestamp(end_ts, timezone.utc)
    return start_utc, end_utc, start_ts, end_ts


def resolve_time_window(args: argparse.Namespace) -> TimeWindow:
    if args.last_hours is not None:
        if args.last_hours <= 0:
            raise SystemExit("--last-hours must be greater than 0")
        end_local = now_in_timezone(args.timezone)
        end_utc = end_local.astimezone(timezone.utc)
        start_utc = end_utc - timedelta(hours=args.last_hours)
        return TimeWindow(
            mode="rolling_hours",
            label=f"last {args.last_hours:g} hours",
            start_utc=start_utc,
            end_utc=end_utc,
            start_ts=int(start_utc.timestamp()),
            end_ts=int(end_utc.timestamp()),
            timezone=args.timezone,
            target_date=None,
            last_hours=args.last_hours,
        )

    if args.date:
        target = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        today = now_in_timezone(args.timezone).date()
        if args.when == "today":
            target = today
        else:
            target = today - timedelta(days=1)

    start_utc, end_utc, start_ts, end_ts = date_bounds(target, args.timezone)
    label = target.isoformat() if args.date else (args.when or "yesterday")
    return TimeWindow(
        mode="calendar_day",
        label=label,
        start_utc=start_utc,
        end_utc=end_utc,
        start_ts=start_ts,
        end_ts=end_ts,
        timezone=args.timezone,
        target_date=target.isoformat(),
        last_hours=None,
    )


def codex_home() -> Path:
    raw = os.environ.get("CODEX_HOME")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".codex"


def index_path(args: argparse.Namespace, home: Path) -> Path:
    if args.index_path:
        return Path(args.index_path).expanduser()
    return home / "sqlite" / "session_message_index.sqlite"


def normalize_path(raw: str) -> str:
    return str(Path(raw).expanduser().resolve(strict=False)).rstrip("/").lower()


def repo_matcher(repo_arg: str) -> tuple[str, str]:
    repo_path = Path(repo_arg).expanduser()
    repo_canon = str(repo_path.resolve(strict=False)).rstrip("/")
    repo_name = repo_path.name.lower()
    return repo_canon.lower(), repo_name


def classify_cwd(
    cwd: str,
    repo_canon: str,
    repo_name: str,
    *,
    allow_basename_fallback: bool,
) -> MatchInfo | None:
    if not cwd:
        return None
    norm = normalize_path(cwd)
    if norm == repo_canon or norm.startswith(repo_canon + "/"):
        return MatchInfo(reason="cwd_within_repo", confidence="high")
    cwd_name = Path(norm).name.lower()
    if cwd_name == repo_name and "/.codex/worktrees/" in norm:
        return MatchInfo(reason="codex_worktree_name_match", confidence="medium")
    if allow_basename_fallback and cwd_name == repo_name:
        return MatchInfo(reason="cwd_basename_match", confidence="low")
    return None


def parse_message_text(content: list[dict]) -> str:
    parts = []
    for item in content:
        text = item.get("text")
        if text:
            parts.append(text)
    return "\n".join(parts)


def strip_wrappers(text: str) -> str:
    text = text.strip()
    for marker in ("</environment_context>", "</INSTRUCTIONS>"):
        if marker in text:
            text = text.split(marker, 1)[1].strip()
    return text.strip()


def classify_message(cleaned_text: str) -> str:
    if not cleaned_text:
        return "empty_after_wrapper"
    if cleaned_text.startswith(TITLE_GENERATOR_PREFIX):
        return "internal_title_generation"
    for prefix, kind in CONTROL_KINDS.items():
        if cleaned_text.startswith(prefix):
            return kind
    return "user_request"


def parse_source_json(source: str) -> dict | None:
    source = (source or "").strip()
    if not source.startswith("{"):
        return None
    try:
        return json.loads(source)
    except json.JSONDecodeError:
        return None


def is_thread_subagent(source: str, agent_role: str | None) -> bool:
    parsed = parse_source_json(source)
    if isinstance(parsed, dict) and "subagent" in parsed:
        return True
    return bool(agent_role)


def iso_utc_from_unix(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat().replace("+00:00", "Z")


def now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_event_timestamp(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def iso_local_from_utc(raw: str | None, timezone_name: str) -> str | None:
    ts = parse_event_timestamp(raw)
    if ts is None:
        return None
    return ts.astimezone(timezone_info(timezone_name)).isoformat()


@lru_cache(maxsize=4096)
def resolve_transcript_path(home: Path, rollout_path: str) -> Path | None:
    if not rollout_path:
        return None
    raw = Path(rollout_path).expanduser()
    if raw.exists():
        return raw
    archived = home / "archived_sessions" / raw.name
    if archived.exists():
        return archived
    scripts_sessions = home / "scripts" / "sessions"
    try:
        relative = raw.relative_to(home / "sessions")
    except ValueError:
        relative = None
    if relative is not None:
        mirrored = scripts_sessions / relative
        if mirrored.exists():
            return mirrored
    matches = list(scripts_sessions.rglob(raw.name))
    if matches:
        return matches[0]
    return None


@lru_cache(maxsize=4096)
def transcript_has_activity_in_window(
    transcript_path: str,
    start_iso: str,
    end_iso: str,
) -> bool:
    start = parse_event_timestamp(start_iso)
    end = parse_event_timestamp(end_iso)
    if start is None or end is None:
        return False
    with Path(transcript_path).open() as handle:
        for raw_line in handle:
            try:
                item = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            ts = parse_event_timestamp(item.get("timestamp"))
            if ts is None:
                continue
            if start <= ts < end:
                return True
    return False


@lru_cache(maxsize=8192)
def logs_have_activity_in_window(home: str, thread_id: str, start_ts: int, end_ts: int) -> bool:
    log_db = Path(home) / "logs_1.sqlite"
    if not log_db.exists():
        return False
    with sqlite3.connect(str(log_db)) as conn:
        row = conn.execute(
            """
            select 1
            from logs
            where thread_id = ?
              and ts >= ?
              and ts < ?
            limit 1
            """,
            (thread_id, start_ts, end_ts),
        ).fetchone()
    return row is not None


def inventory_sessions_from_state(
    home: Path,
    window: TimeWindow,
    repo_canon: str,
    repo_name: str,
    include_subagents: bool,
    allow_basename_fallback: bool,
) -> list[InventoryThread]:
    db_path = home / "state_5.sqlite"
    if not db_path.exists():
        return []

    rows: list[InventoryThread] = []
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        for row in conn.execute(
            """
            select id, rollout_path, created_at, updated_at, cwd, source, agent_role, first_user_message
            from threads
            where created_at < ?
              and updated_at >= ?
            order by created_at, id
            """,
            (window.end_ts, window.start_ts),
        ):
            match = classify_cwd(
                row["cwd"],
                repo_canon,
                repo_name,
                allow_basename_fallback=allow_basename_fallback,
            )
            if not match:
                continue
            if is_thread_subagent(row["source"], row["agent_role"]) and not include_subagents:
                continue

            created_at = int(row["created_at"])
            updated_at = int(row["updated_at"])
            rollout_path = row["rollout_path"]
            transcript_path = resolve_transcript_path(home, rollout_path)

            inventory_reasons: list[str] = []
            if window.start_ts <= created_at < window.end_ts:
                inventory_reasons.append(
                    "created_in_window"
                    if window.mode == "rolling_hours"
                    else "created_on_day"
                )
            if window.start_ts <= updated_at < window.end_ts:
                inventory_reasons.append(
                    "state_updated_in_window"
                    if window.mode == "rolling_hours"
                    else "state_updated_on_day"
                )
            if transcript_path and transcript_has_activity_in_window(
                str(transcript_path),
                window.start_utc.isoformat(),
                window.end_utc.isoformat(),
            ):
                inventory_reasons.append(
                    "transcript_activity_in_window"
                    if window.mode == "rolling_hours"
                    else "transcript_activity_on_day"
                )
            elif logs_have_activity_in_window(str(home), row["id"], window.start_ts, window.end_ts):
                inventory_reasons.append(
                    "log_activity_in_window"
                    if window.mode == "rolling_hours"
                    else "log_activity_on_day"
                )

            inventory_reasons = dedupe_keep_order(inventory_reasons)
            if not inventory_reasons:
                continue

            rows.append(
                InventoryThread(
                    thread_id=row["id"],
                    created_at=created_at,
                    updated_at=updated_at,
                    started_at=iso_utc_from_unix(created_at),
                    cwd=row["cwd"],
                    match_reason=match.reason,
                    match_confidence=match.confidence,
                    inventory_reasons=inventory_reasons,
                    rollout_path=rollout_path,
                    transcript_path=str(transcript_path) if transcript_path else None,
                    first_user_message=row["first_user_message"] or "",
                )
            )
    return rows


def load_assistant_tail(transcript_path: str | None) -> str:
    if not transcript_path:
        return ""
    tail = ""
    with Path(transcript_path).open() as handle:
        for raw_line in handle:
            try:
                item = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            if item.get("type") != "response_item":
                continue
            payload = item.get("payload", {})
            if payload.get("type") != "message" or payload.get("role") != "assistant":
                continue
            text = strip_wrappers(parse_message_text(payload.get("content", [])))
            if text:
                tail = collapse_ws(text)[:500]
    return tail


def recover_from_rollout(transcript_path: str) -> list[RecoveredMessage]:
    recovered: list[RecoveredMessage] = []
    ordinal = 0
    with Path(transcript_path).open() as handle:
        for raw_line in handle:
            try:
                item = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            if item.get("type") != "response_item":
                continue
            payload = item.get("payload", {})
            if payload.get("type") != "message" or payload.get("role") != "user":
                continue
            raw_text = parse_message_text(payload.get("content", []))
            cleaned = strip_wrappers(raw_text)
            ordinal += 1
            recovered.append(
                RecoveredMessage(
                    ordinal=ordinal,
                    turn_id=None,
                    role="user",
                    kind=classify_message(cleaned),
                    raw_text=raw_text,
                    cleaned_text=cleaned,
                    source="rollout",
                )
            )
    return recovered


def rollout_recovery_status(messages: list[RecoveredMessage]) -> tuple[bool, str]:
    if not messages:
        return False, "rollout transcript contained no user messages"
    meaningful = [
        message
        for message in messages
        if message.kind not in {"empty_after_wrapper", "internal_title_generation"}
    ]
    if not meaningful:
        return False, "rollout transcript contained no meaningful user requests"
    return True, "rollout transcript parsed successfully"


def extract_turn_id(log_body: str) -> str | None:
    match = TURN_ID_RE.search(log_body)
    return match.group(1) if match else None


def parse_response_create_payload(log_body: str) -> dict | None:
    marker = "websocket request: "
    idx = log_body.find(marker)
    if idx == -1:
        return None
    raw = log_body[idx + len(marker) :].strip()
    if not raw.startswith("{"):
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if payload.get("type") != "response.create":
        return None
    return payload


def recover_from_logs(home: Path, thread_id: str) -> tuple[list[RecoveredMessage], str, bool]:
    log_db = home / "logs_1.sqlite"
    if not log_db.exists():
        return [], "logs database missing", False

    messages: list[RecoveredMessage] = []
    seen_turns: set[str] = set()
    complete = True

    with sqlite3.connect(str(log_db)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            select id, feedback_log_body
            from logs
            where thread_id = ?
              and target = 'codex_api::endpoint::responses_websocket'
              and feedback_log_body like '%response.create%'
            order by id asc
            """,
            (thread_id,),
        ).fetchall()

    ordinal = 0
    for row in rows:
        log_body = row["feedback_log_body"] or ""
        turn_id = extract_turn_id(log_body)
        if not turn_id or turn_id in seen_turns:
            continue
        payload = parse_response_create_payload(log_body)
        if payload is None:
            continue
        seen_turns.add(turn_id)

        input_items = payload.get("input")
        turn_messages: list[RecoveredMessage] = []
        if isinstance(input_items, list):
            for item in input_items:
                if not isinstance(item, dict):
                    continue
                if item.get("type") != "message" or item.get("role") != "user":
                    continue
                raw_text = parse_message_text(item.get("content", []))
                cleaned = strip_wrappers(raw_text)
                ordinal += 1
                turn_messages.append(
                    RecoveredMessage(
                        ordinal=ordinal,
                        turn_id=turn_id,
                        role="user",
                        kind=classify_message(cleaned),
                        raw_text=raw_text,
                        cleaned_text=cleaned,
                        source="logs_response_create",
                    )
                )

        meaningful = [
            message
            for message in turn_messages
            if message.kind not in {"empty_after_wrapper", "internal_title_generation"}
        ]
        if not meaningful:
            complete = False
        messages.extend(turn_messages)

    if not seen_turns:
        return [], "no parseable response.create requests found in logs", False
    if not messages:
        return [], "logs contained response.create requests but no user messages", False
    if not complete:
        return messages, "at least one turn lacked a recoverable user message in logs", False
    return messages, "all logged turns carried recoverable user messages", True


def prepend_first_user_fallback(
    messages: list[RecoveredMessage], first_user_message: str
) -> list[RecoveredMessage]:
    if not first_user_message.strip():
        return messages
    meaningful = [
        message
        for message in messages
        if message.kind == "user_request" and collapse_ws(message.cleaned_text)
    ]
    first_collapsed = collapse_ws(first_user_message)
    if meaningful and collapse_ws(meaningful[0].cleaned_text) == first_collapsed:
        return messages

    shifted = [
        RecoveredMessage(
            ordinal=message.ordinal + 1,
            turn_id=message.turn_id,
            role=message.role,
            kind=message.kind,
            raw_text=message.raw_text,
            cleaned_text=message.cleaned_text,
            source=message.source,
        )
        for message in messages
    ]
    return [
        RecoveredMessage(
            ordinal=1,
            turn_id=None,
            role="user",
            kind="user_request",
            raw_text=first_user_message,
            cleaned_text=first_user_message.strip(),
            source="state_first_user_message",
        ),
        *shifted,
    ]


def sync_thread(home: Path, item: InventoryThread) -> ThreadSyncResult:
    assistant_tail = load_assistant_tail(item.transcript_path)
    if item.transcript_path:
        messages = recover_from_rollout(item.transcript_path)
        rollout_complete, rollout_reason = rollout_recovery_status(messages)
        if rollout_complete:
            return ThreadSyncResult(
                thread_id=item.thread_id,
                created_at=item.created_at,
                updated_at=item.updated_at,
                started_at=item.started_at,
                cwd=item.cwd,
                match_reason=item.match_reason,
                match_confidence=item.match_confidence,
                inventory_reasons=item.inventory_reasons,
                rollout_path=item.rollout_path,
                transcript_path=item.transcript_path,
                transcript_available=True,
                first_user_message=item.first_user_message,
                sync_source="rollout",
                completeness_status="complete",
                completeness_reason=rollout_reason,
                assistant_tail=assistant_tail,
                messages=messages,
            )

        log_messages, log_reason, log_complete = recover_from_logs(home, item.thread_id)
        if log_complete:
            return ThreadSyncResult(
                thread_id=item.thread_id,
                created_at=item.created_at,
                updated_at=item.updated_at,
                started_at=item.started_at,
                cwd=item.cwd,
                match_reason=item.match_reason,
                match_confidence=item.match_confidence,
                inventory_reasons=item.inventory_reasons,
                rollout_path=item.rollout_path,
                transcript_path=item.transcript_path,
                transcript_available=True,
                first_user_message=item.first_user_message,
                sync_source="logs_response_create",
                completeness_status="complete",
                completeness_reason=f"{rollout_reason}; fully recovered from logs instead",
                assistant_tail=assistant_tail,
                messages=log_messages,
            )

        fallback_messages = prepend_first_user_fallback(log_messages, item.first_user_message)
        fallback_reason = f"{rollout_reason}; {log_reason}"
        if item.first_user_message.strip():
            fallback_reason += "; fell back to state first_user_message for partial coverage"
            sync_source = "mixed_partial"
        else:
            sync_source = "logs_response_create"

        return ThreadSyncResult(
            thread_id=item.thread_id,
            created_at=item.created_at,
            updated_at=item.updated_at,
            started_at=item.started_at,
            cwd=item.cwd,
            match_reason=item.match_reason,
            match_confidence=item.match_confidence,
            inventory_reasons=item.inventory_reasons,
            rollout_path=item.rollout_path,
            transcript_path=item.transcript_path,
            transcript_available=True,
            first_user_message=item.first_user_message,
            sync_source=sync_source,
            completeness_status="incomplete",
            completeness_reason=fallback_reason,
            assistant_tail=assistant_tail,
            messages=fallback_messages,
        )

    log_messages, log_reason, log_complete = recover_from_logs(home, item.thread_id)
    if log_complete:
        return ThreadSyncResult(
            thread_id=item.thread_id,
            created_at=item.created_at,
            updated_at=item.updated_at,
            started_at=item.started_at,
            cwd=item.cwd,
            match_reason=item.match_reason,
            match_confidence=item.match_confidence,
            inventory_reasons=item.inventory_reasons,
            rollout_path=item.rollout_path,
            transcript_path=None,
            transcript_available=False,
            first_user_message=item.first_user_message,
            sync_source="logs_response_create",
            completeness_status="complete",
            completeness_reason=log_reason,
            assistant_tail="",
            messages=log_messages,
        )

    messages = prepend_first_user_fallback(log_messages, item.first_user_message)
    fallback_reason = log_reason
    if item.first_user_message.strip():
        fallback_reason += "; fell back to state first_user_message for partial coverage"
        sync_source = "mixed_partial"
    else:
        sync_source = "logs_response_create"

    return ThreadSyncResult(
        thread_id=item.thread_id,
        created_at=item.created_at,
        updated_at=item.updated_at,
        started_at=item.started_at,
        cwd=item.cwd,
        match_reason=item.match_reason,
        match_confidence=item.match_confidence,
        inventory_reasons=item.inventory_reasons,
        rollout_path=item.rollout_path,
        transcript_path=None,
        transcript_available=False,
        first_user_message=item.first_user_message,
        sync_source=sync_source,
        completeness_status="incomplete",
        completeness_reason=fallback_reason,
        assistant_tail="",
        messages=messages,
    )


def ensure_index_schema(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(INDEX_SCHEMA)
        conn.commit()


def write_sync_results(db_path: Path, results: list[ThreadSyncResult]) -> None:
    ensure_index_schema(db_path)
    synced_at = now_iso_utc()
    with sqlite3.connect(str(db_path)) as conn:
        for result in results:
            conn.execute("delete from messages where thread_id = ?", (result.thread_id,))
            conn.execute(
                """
                insert into threads (
                    thread_id, created_at, started_at, cwd, match_reason,
                    rollout_path, transcript_path, transcript_available,
                    first_user_message, sync_source, completeness_status,
                    completeness_reason, synced_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(thread_id) do update set
                    created_at = excluded.created_at,
                    started_at = excluded.started_at,
                    cwd = excluded.cwd,
                    match_reason = excluded.match_reason,
                    rollout_path = excluded.rollout_path,
                    transcript_path = excluded.transcript_path,
                    transcript_available = excluded.transcript_available,
                    first_user_message = excluded.first_user_message,
                    sync_source = excluded.sync_source,
                    completeness_status = excluded.completeness_status,
                    completeness_reason = excluded.completeness_reason,
                    synced_at = excluded.synced_at
                """,
                (
                    result.thread_id,
                    result.created_at,
                    result.started_at,
                    result.cwd,
                    result.match_reason,
                    result.rollout_path,
                    result.transcript_path,
                    1 if result.transcript_available else 0,
                    result.first_user_message,
                    result.sync_source,
                    result.completeness_status,
                    result.completeness_reason,
                    synced_at,
                ),
            )
            for message in result.messages:
                conn.execute(
                    """
                    insert into messages (
                        thread_id, ordinal, turn_id, role, kind,
                        raw_text, cleaned_text, source
                    ) values (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        result.thread_id,
                        message.ordinal,
                        message.turn_id,
                        message.role,
                        message.kind,
                        message.raw_text,
                        message.cleaned_text,
                        message.source,
                    ),
                )
        conn.commit()


def git_summary(repo: str) -> dict | None:
    repo_path = Path(repo).expanduser()
    if not repo_path.exists():
        return None

    def run_git(*args: str) -> tuple[int, str]:
        result = subprocess.run(
            ["git", "-C", str(repo_path), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode, result.stdout.strip()

    def run_git_or_empty(*args: str) -> str:
        _, output = run_git(*args)
        return output

    def rev_list_counts(left: str, right: str) -> dict | None:
        code, output = run_git("rev-list", "--left-right", "--count", f"{left}...{right}")
        if code != 0 or not output:
            return None
        parts = output.split()
        if len(parts) != 2:
            return None
        try:
            behind = int(parts[0])
            ahead = int(parts[1])
        except ValueError:
            return None
        return {"behind": behind, "ahead": ahead}

    branch = run_git_or_empty("branch", "--show-current")
    status = run_git_or_empty("status", "--short")
    log = run_git_or_empty("log", "--oneline", "--decorate", "-n", "20")

    upstream = None
    upstream_code, upstream_output = run_git(
        "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"
    )
    if upstream_code == 0 and upstream_output:
        upstream = upstream_output

    summary = {
        "captured_at": now_iso_utc(),
        "branch": branch,
        "status_clean": not bool(status.strip()),
        "status_short": status.splitlines() if status else [],
        "recent_log": log.splitlines() if log else [],
        "note": (
            "This is the current repo state at digest time. Treat it as supplementary "
            "context, not as proof of the target day's state."
        ),
    }
    if upstream:
        summary["upstream"] = upstream
        upstream_divergence = rev_list_counts("@{upstream}", "HEAD")
        if upstream_divergence is not None:
            summary["upstream_divergence"] = upstream_divergence
    if branch and branch != "main":
        main_divergence = rev_list_counts("main", "HEAD")
        if main_divergence is not None:
            summary["main_divergence"] = main_divergence
            summary["branch_summary"] = (
                f"`{branch}` is {main_divergence['ahead']} commit(s) ahead of `main` and "
                f"{main_divergence['behind']} behind."
            )
    return summary


def classify_session_outcome(user_messages: list[dict], assistant_tail: str) -> dict:
    tail = collapse_ws(assistant_tail).lower()
    user_texts = [collapse_ws(message["text"]) for message in user_messages]
    all_user = " ".join(user_texts).lower()
    last_user = user_texts[-1].lower() if user_texts else ""

    evidence: list[str] = []
    status = "unknown"
    confidence = "low"

    if "handover" in all_user and contains_any(tail, PUSH_MARKERS):
        status = "handover_only"
        confidence = "high"
        evidence.append("user asked for a handover and the assistant tail shows a push")
    elif contains_any(tail, MERGE_MARKERS):
        status = "implemented_and_merged"
        confidence = "high"
        evidence.append("assistant tail contains merge/PR markers")
    elif contains_any(tail, PUSH_MARKERS):
        status = "implemented_and_pushed"
        confidence = "high"
        evidence.append("assistant tail contains push markers")
    elif contains_any(tail, COMMIT_MARKERS) and not contains_any(tail, PUSH_MARKERS):
        status = "implemented_local_only"
        confidence = "medium"
        evidence.append("assistant tail contains commit markers without a push marker")
    elif contains_any(tail, BLOCKED_MARKERS):
        status = "blocked_waiting_for_input"
        confidence = "high"
        evidence.append("assistant tail explicitly asks the user for missing inputs")
    elif contains_any(last_user, PLAN_MARKERS) and not contains_any(tail, PUSH_MARKERS + MERGE_MARKERS):
        status = "plan_only"
        confidence = "high"
        evidence.append("latest user request explicitly asked for planning without changes")
    elif contains_any(all_user, INVESTIGATION_MARKERS) and not contains_any(
        tail, PUSH_MARKERS + MERGE_MARKERS + COMMIT_MARKERS
    ):
        status = "investigation_only"
        confidence = "medium"
        evidence.append("thread emphasizes investigation/root-cause analysis without landing work")
    elif contains_any(tail, LOCAL_IMPLEMENTATION_MARKERS):
        status = "implemented_local_only"
        confidence = "medium"
        evidence.append("assistant tail describes concrete local code changes")
    elif contains_any(all_user, QUESTION_MARKERS) and not contains_any(
        all_user, PLAN_MARKERS + INVESTIGATION_MARKERS
    ):
        status = "question_answered"
        confidence = "medium"
        evidence.append("thread is primarily explanatory rather than execution-oriented")
    else:
        evidence.append("no strong completion or blockage marker found")

    return {
        "status": status,
        "confidence": confidence,
        "evidence": evidence,
    }


def combined_session_text(session: dict) -> str:
    return (
        " ".join(message["text"] for message in session["user_messages"]).lower()
        + " "
        + session["assistant_tail"].lower()
    )


def user_text(session: dict) -> str:
    return " ".join(message["text"] for message in session["user_messages"]).lower()


def priority_signals_for_session(session: dict) -> list[str]:
    combined = combined_session_text(session)
    signals: list[str] = []
    if contains_any(combined, URGENT_MARKERS):
        signals.append("urgent production/release language appears in the thread")
    if contains_any(combined, VERIFICATION_MARKERS):
        signals.append("user explicitly asked for live verification or action polling")
    if contains_any(combined, NEXT_STEP_MARKERS):
        signals.append("user explicitly asked what should happen next")
    if contains_any(combined, EXECUTION_OWNERSHIP_MARKERS):
        signals.append("user pushed execution ownership onto the agent, not just planning")
    return signals


def is_low_signal_operational_session(session: dict) -> bool:
    combined = combined_session_text(session)
    if contains_any(combined, URGENT_MARKERS + PLAN_MARKERS + INVESTIGATION_MARKERS):
        return False
    if len(session["user_messages"]) > 2:
        return False
    return contains_any(combined, LOW_SIGNAL_OPERATIONAL_MARKERS)


def theme_for_session(session: dict) -> tuple[str, str]:
    combined = combined_session_text(session)

    if "posthog" in combined:
        return ("posthog", "Implement the self-hosted PostHog plan")
    if contains_any(combined, ("new tenant", "provision a new tenant", "privision a new tenant")):
        return ("tenant_provisioning", "Provision the next tenant once inputs and access are confirmed")
    if contains_any(
        combined,
        (
            "structured output",
            "structured outputs",
            "json-backed",
            "generate json",
            "output schema",
            "automation outputs",
        ),
    ):
        return ("automation_json_outputs", "Finish the JSON-backed automation output direction")
    if contains_any(
        combined,
        (
            "release gate",
            "release rollout",
            "loader_runtime",
            "dynamic worker",
            "github actions",
            "workflow",
            "stale frontend",
            "no llm response",
            "hosted automation detail",
            "cloudflare",
        ),
    ):
        return ("release_rollout", "Repair the rollout and hosted release-proof path")
    if contains_any(combined, ("launch_grant", "/auth/launch", "studio_access", "signing up")):
        return ("auth_flow", "Clarify and refine the hosted auth flow")
    if contains_any(
        combined,
        (
            "dark mode",
            "/dashboard",
            "/automations",
            "/connections",
            "automations page",
            "dashboard looks",
            "frontend bug",
            "dark mode is messed up",
            "dropdown menu gets cut off",
        ),
    ):
        return ("ui_refinement", "Continue the dashboard and automations UI refinement work")

    first = collapse_ws(session["user_messages"][0]["text"]) if session["user_messages"] else "Follow up"
    if len(first) > 80:
        first = first[:77].rstrip() + "..."
    return (f"session:{session['session_id']}", first)


def session_priority_score(session: dict, index: int) -> int:
    if is_low_signal_operational_session(session):
        return 0

    status = session["outcome"]["status"]
    if status in TERMINAL_OUTCOME_STATUSES:
        return 0

    base = {
        "plan_only": 20,
        "investigation_only": 30,
        "blocked_waiting_for_input": 12,
        "implemented_local_only": 18,
        "unknown": 10,
    }.get(status, 10)

    combined = combined_session_text(session)
    if contains_any(combined, URGENT_MARKERS):
        base += 55
    if contains_any(combined, VERIFICATION_MARKERS):
        base += 20
    if contains_any(combined, NEXT_STEP_MARKERS):
        base += 10
    if contains_any(combined, EXECUTION_OWNERSHIP_MARKERS):
        base += 8
    if session["match_confidence"] == "medium":
        base -= 5
    if session["match_confidence"] == "low":
        base -= 20
    base += index
    return max(base, 0)


def infer_theme_current_state(sessions: list[dict]) -> tuple[str, str, dict]:
    ordered = sorted(sessions, key=lambda item: (item["started_at"], item["filename"]))
    focus = ordered[-1]
    for session in reversed(ordered):
        if session["outcome"]["status"] not in TERMINAL_OUTCOME_STATUSES:
            focus = session
            break

    focus_status = focus["outcome"]["status"]
    earlier_statuses = [session["outcome"]["status"] for session in ordered if session is not focus]
    has_landed = any(
        status in {"implemented_and_merged", "implemented_and_pushed", "handover_only"}
        for status in earlier_statuses
    )
    has_local_only = any(status == "implemented_local_only" for status in earlier_statuses)

    if focus_status == "blocked_waiting_for_input":
        return (
            "blocked_waiting_for_input",
            "latest active session is blocked on missing user inputs",
            focus,
        )
    if focus_status == "implemented_local_only":
        return (
            "in_flight_unlanded",
            "latest active session shows local implementation without landing evidence yet",
            focus,
        )
    if focus_status in {"plan_only", "investigation_only", "unknown"}:
        if has_landed:
            return (
                "implemented_but_unverified",
                "earlier sessions landed changes, but the latest active session is still verifying or debugging the real outcome",
                focus,
            )
        if has_local_only:
            return (
                "in_flight_unlanded",
                "earlier session shows local implementation and the latest active session is still following up",
                focus,
            )
        if focus_status == "unknown":
            return ("needs_triage", "latest active session did not expose a clear completion marker", focus)
        return (focus_status, f"latest active session remains `{focus_status}`", focus)
    if focus_status == "implemented_and_merged":
        return ("done", "latest session appears merged", focus)
    if focus_status == "implemented_and_pushed":
        return ("implemented_but_unverified", "latest session pushed code but did not prove the final outcome", focus)
    if focus_status == "handover_only":
        return ("handover_only", "latest session produced a handover instead of final proof", focus)
    if focus_status == "question_answered":
        return ("question_answered", "latest session was explanatory rather than execution-oriented", focus)
    return ("needs_triage", "theme state needs manual interpretation", focus)


def build_theme_summaries(sessions: list[dict], timezone_name: str) -> list[dict]:
    grouped: dict[str, dict] = {}
    for index, session in enumerate(sessions, start=1):
        score = session_priority_score(session, index)
        key, title = theme_for_session(session)
        bucket = grouped.setdefault(
            key,
            {
                "theme_key": key,
                "title": title,
                "score": 0,
                "sessions": [],
                "statuses": Counter(),
                "why": [],
                "priority_signals": [],
                "latest_started_at": session["started_at"],
            },
        )
        bucket["score"] += score
        bucket["sessions"].append(
            {
                "session_id": session["session_id"],
                "filename": session["filename"],
                "started_at": session["started_at"],
                "started_at_local": iso_local_from_utc(session["started_at"], timezone_name),
                "outcome_status": session["outcome"]["status"],
                "low_signal_operational": is_low_signal_operational_session(session),
            }
        )
        bucket["statuses"][session["outcome"]["status"]] += 1
        bucket["latest_started_at"] = max(bucket["latest_started_at"], session["started_at"])
        for reason in session["outcome"]["evidence"]:
            if reason not in bucket["why"]:
                bucket["why"].append(reason)
        for signal in priority_signals_for_session(session):
            if signal not in bucket["priority_signals"]:
                bucket["priority_signals"].append(signal)

    summaries = []
    for bucket in grouped.values():
        theme_sessions = [
            session
            for session in sessions
            if theme_for_session(session)[0] == bucket["theme_key"]
        ]
        current_state, current_state_reason, focus = infer_theme_current_state(theme_sessions)
        ordered_sessions = sorted(
            bucket["sessions"],
            key=lambda item: (item["started_at"], item["filename"]),
        )
        summaries.append(
            {
                "theme_key": bucket["theme_key"],
                "title": bucket["title"],
                "score": bucket["score"],
                "current_state": current_state,
                "current_state_reason": current_state_reason,
                "latest_outcome_status": focus["outcome"]["status"],
                "priority_signals": bucket["priority_signals"],
                "why": bucket["why"][:3],
                "sessions": ordered_sessions,
                "session_count": len(ordered_sessions),
                "latest_started_at": bucket["latest_started_at"],
                "latest_started_at_local": iso_local_from_utc(bucket["latest_started_at"], timezone_name),
                "landed_session_count": sum(
                    1
                    for session in theme_sessions
                    if session["outcome"]["status"] in {"implemented_and_merged", "implemented_and_pushed"}
                ),
                "local_only_session_count": sum(
                    1 for session in theme_sessions if session["outcome"]["status"] == "implemented_local_only"
                ),
                "blocked_session_count": sum(
                    1
                    for session in theme_sessions
                    if session["outcome"]["status"] == "blocked_waiting_for_input"
                ),
                "low_signal_operational": all(
                    session["low_signal_operational"] for session in ordered_sessions
                ),
                "superseded_session_ids": [
                    session["session_id"]
                    for session in ordered_sessions
                    if session["session_id"] != focus["session_id"]
                ],
                "focus_session_id": focus["session_id"],
            }
        )

    summaries.sort(
        key=lambda item: (item["score"], item["session_count"], item["latest_started_at"]),
        reverse=True,
    )
    return summaries


def build_candidate_next_actions(theme_summaries: list[dict]) -> list[dict]:
    candidates = []
    for item in theme_summaries:
        if item["score"] <= 0 or item["low_signal_operational"]:
            continue
        if item["current_state"] in {"done", "handover_only", "question_answered"}:
            continue
        candidates.append(
            {
                "theme_key": item["theme_key"],
                "title": item["title"],
                "score": item["score"],
                "status_guess": item["current_state"],
                "why": [item["current_state_reason"], *item["priority_signals"]][:3],
                "supporting_sessions": item["sessions"],
                "supporting_session_count": item["session_count"],
                "latest_started_at": item["latest_started_at"],
                "latest_started_at_local": item["latest_started_at_local"],
            }
        )

    candidates.sort(
        key=lambda item: (item["score"], item["supporting_session_count"], item["latest_started_at"]),
        reverse=True,
    )
    return candidates


def build_payload(args: argparse.Namespace) -> dict:
    window = resolve_time_window(args)
    home = codex_home()
    repo_canon, repo_name = repo_matcher(args.repo)
    inventory = inventory_sessions_from_state(
        home=home,
        window=window,
        repo_canon=repo_canon,
        repo_name=repo_name,
        include_subagents=args.include_subagents,
        allow_basename_fallback=args.allow_basename_fallback,
    )
    results = [sync_thread(home, item) for item in inventory]
    write_sync_results(index_path(args, home), results)

    sessions = []
    user_request_count = 0
    aggregate_controls: Counter[str] = Counter()
    incomplete_threads = []
    outcome_counts: Counter[str] = Counter()
    theme_counts: Counter[str] = Counter()

    for result in results:
        display_messages = []
        session_controls: Counter[str] = Counter()
        for message in result.messages:
            if message.kind == "user_request":
                user_request_count += 1
                display_messages.append(
                    {
                        "ordinal": message.ordinal,
                        "kind": message.kind,
                        "text": message.cleaned_text,
                        "source": message.source,
                        "turn_id": message.turn_id,
                    }
                )
            else:
                session_controls[message.kind] += 1
        aggregate_controls.update(session_controls)

        session = {
            "session_id": result.thread_id,
            "filename": Path(result.rollout_path).name,
            "path": result.rollout_path,
            "transcript_path": result.transcript_path,
            "started_at": result.started_at,
            "started_at_local": iso_local_from_utc(result.started_at, args.timezone),
            "cwd": result.cwd,
            "match_reason": result.match_reason,
            "match_confidence": result.match_confidence,
            "inventory_reasons": result.inventory_reasons,
            "assistant_tail": result.assistant_tail,
            "sync_source": result.sync_source,
            "completeness_status": result.completeness_status,
            "completeness_reason": result.completeness_reason,
            "transcript_available": result.transcript_available,
            "control_counts": dict(sorted(session_controls.items())),
            "user_messages": display_messages,
        }
        session["outcome"] = classify_session_outcome(display_messages, result.assistant_tail)
        theme_key, theme_title = theme_for_session(session)
        session["theme"] = {"key": theme_key, "title": theme_title}
        session["low_signal_operational"] = is_low_signal_operational_session(session)
        session["priority_signals"] = priority_signals_for_session(session)

        sessions.append(session)
        outcome_counts[session["outcome"]["status"]] += 1
        theme_counts[theme_key] += 1

        if result.completeness_status != "complete":
            incomplete_threads.append(
                {
                    "session_id": result.thread_id,
                    "filename": Path(result.rollout_path).name,
                    "started_at": result.started_at,
                    "cwd": result.cwd,
                    "sync_source": result.sync_source,
                    "reason": result.completeness_reason,
                }
            )

    sessions.sort(key=lambda item: (item["started_at"], item["filename"]))
    incomplete_threads.sort(key=lambda item: (item["started_at"], item["filename"]))
    theme_summaries = build_theme_summaries(sessions, args.timezone)
    candidate_next_actions = build_candidate_next_actions(theme_summaries)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "complete" if not incomplete_threads else "incomplete",
        "repo": {
            "input": args.repo,
            "canonical_path": repo_canon,
            "name": repo_name,
        },
        "target_mode": window.mode,
        "target_date": window.target_date,
        "target_window": {
            "mode": window.mode,
            "label": window.label,
            "start_at": window.start_utc.isoformat().replace("+00:00", "Z"),
            "start_at_local": window.start_utc.astimezone(timezone_info(args.timezone)).isoformat(),
            "end_at": window.end_utc.isoformat().replace("+00:00", "Z"),
            "end_at_local": window.end_utc.astimezone(timezone_info(args.timezone)).isoformat(),
            "timezone": window.timezone,
            "last_hours": window.last_hours,
        },
        "timezone": args.timezone,
        "code_home": str(home),
        "index_path": str(index_path(args, home)),
        "session_inventory_count": len(inventory),
        "relevant_sessions": sessions,
        "totals": {
            "relevant_session_count": len(sessions),
            "complete_session_count": len(sessions) - len(incomplete_threads),
            "incomplete_session_count": len(incomplete_threads),
            "user_request_count": user_request_count,
            "control_counts": dict(sorted(aggregate_controls.items())),
        },
        "historical_evidence": {
            "outcome_counts": dict(sorted(outcome_counts.items())),
            "theme_counts": dict(sorted(theme_counts.items())),
            "low_signal_operational_session_count": sum(
                1 for session in sessions if session["low_signal_operational"]
            ),
            "note": (
                "These fields are derived from target-day session evidence. Prefer this "
                "over current repo state when reconstructing what happened in the target "
                "window."
            ),
        },
        "theme_summaries": theme_summaries,
        "candidate_next_actions": candidate_next_actions,
        "incomplete_threads": incomplete_threads,
    }
    if args.include_git:
        payload["current_repo_state"] = {"git": git_summary(args.repo)}
    return payload


def render_markdown(payload: dict) -> str:
    lines = []
    window = payload["target_window"]
    lines.append("# Repo Session Digest")
    lines.append("")
    lines.append(f"- Schema version: `{payload['schema_version']}`")
    lines.append(f"- Status: `{payload['status'].upper()}`")
    lines.append(f"- Repo: `{payload['repo']['input']}`")
    lines.append(f"- Canonical path: `{payload['repo']['canonical_path']}`")
    if payload["target_mode"] == "calendar_day":
        lines.append(f"- Target date: `{payload['target_date']}`")
    else:
        lines.append(f"- Target window: `{window['label']}`")
    lines.append(f"- Window start: `{window['start_at']}`")
    lines.append(f"- Window start ({window['timezone']}): `{window['start_at_local']}`")
    lines.append(f"- Window end: `{window['end_at']}`")
    lines.append(f"- Window end ({window['timezone']}): `{window['end_at_local']}`")
    lines.append(f"- Window timezone: `{window['timezone']}`")
    lines.append(f"- Matching top-level threads inventoried: {payload['session_inventory_count']}")
    lines.append(f"- Relevant top-level sessions: {payload['totals']['relevant_session_count']}")
    lines.append(f"- Fully recovered sessions: {payload['totals']['complete_session_count']}")
    lines.append(f"- Incomplete sessions: {payload['totals']['incomplete_session_count']}")
    lines.append(f"- User requests extracted: {payload['totals']['user_request_count']}")
    lines.append(f"- Canonical index: `{payload['index_path']}`")
    if payload["totals"]["control_counts"]:
        controls = ", ".join(
            f"{kind}={count}" for kind, count in payload["totals"]["control_counts"].items()
        )
        lines.append(f"- Control messages skipped: {controls}")

    if payload["candidate_next_actions"]:
        lines.append("")
        lines.append("## Candidate Next Actions")
        lines.append("")
        for index, item in enumerate(payload["candidate_next_actions"], start=1):
            lines.append(f"{index}. {item['title']} (score {item['score']})")
            if item["why"]:
                lines.append(f"   Why: {'; '.join(item['why'])}")
            lines.append(
                "   Sessions: "
                + ", ".join(
                    f"`{session['filename']}` ({session['outcome_status']})"
                    for session in item["supporting_sessions"][:4]
                )
            )

    lines.append("")
    lines.append("## Historical Evidence")
    lines.append("")
    lines.append(f"- Note: {payload['historical_evidence']['note']}")
    outcome_counts = payload["historical_evidence"]["outcome_counts"]
    if outcome_counts:
        lines.append(
            "- Outcome counts: "
            + ", ".join(f"`{kind}`={count}" for kind, count in outcome_counts.items())
        )
    theme_counts = payload["historical_evidence"]["theme_counts"]
    if theme_counts:
        lines.append(
            "- Theme counts: "
            + ", ".join(f"`{kind}`={count}" for kind, count in theme_counts.items())
        )
    lines.append(
        "- Low-signal operational sessions: "
        + str(payload["historical_evidence"].get("low_signal_operational_session_count", 0))
    )

    if payload.get("theme_summaries"):
        lines.append("")
        lines.append("## Theme Summaries")
        lines.append("")
        for item in payload["theme_summaries"]:
            lines.append(f"- `{item['theme_key']}`: {item['title']}")
            lines.append(
                f"  current state: `{item['current_state']}`; latest: `{item['latest_started_at']}`"
            )
            lines.append(f"  reason: {item['current_state_reason']}")
            lines.append(
                "  counts: "
                f"sessions={item['session_count']}, landed={item['landed_session_count']}, "
                f"local_only={item['local_only_session_count']}, blocked={item['blocked_session_count']}"
            )
            if item["priority_signals"]:
                lines.append("  priority signals: " + "; ".join(item["priority_signals"]))
            if item["superseded_session_ids"]:
                lines.append(
                    "  superseded sessions: "
                    + ", ".join(f"`{session_id}`" for session_id in item["superseded_session_ids"][:6])
                )

    if payload["incomplete_threads"]:
        lines.append("")
        lines.append("## Incomplete Threads")
        lines.append("")
        lines.append(
            "The digest is incomplete. Do not synthesize a final recommendation from this "
            "result unless you explicitly allow incomplete coverage."
        )
        lines.append("")
        for item in payload["incomplete_threads"]:
            lines.append(f"- `{item['filename']}` `{item['started_at']}` `{item['sync_source']}`")
            lines.append(f"  reason: {item['reason']}")

    current_repo_state = payload.get("current_repo_state", {})
    git = current_repo_state.get("git")
    if git:
        lines.append("")
        lines.append("## Current Repo State")
        lines.append("")
        lines.append(f"- Captured at: `{git['captured_at']}`")
        lines.append(f"- Note: {git['note']}")
        lines.append(f"- Branch: `{git['branch']}`")
        lines.append(f"- Worktree clean: {'yes' if git['status_clean'] else 'no'}")
        if git.get("branch_summary"):
            lines.append(f"- Branch summary: {git['branch_summary']}")
        if git.get("upstream"):
            lines.append(f"- Upstream: `{git['upstream']}`")
        if git.get("upstream_divergence"):
            lines.append(
                "- Upstream divergence: "
                f"ahead={git['upstream_divergence']['ahead']}, "
                f"behind={git['upstream_divergence']['behind']}"
            )
        if git.get("main_divergence"):
            lines.append(
                "- Main divergence: "
                f"ahead={git['main_divergence']['ahead']}, "
                f"behind={git['main_divergence']['behind']}"
            )
        if git["status_short"]:
            lines.append("- Status:")
            lines.extend([f"  `{row}`" for row in git["status_short"]])
        if git["recent_log"]:
            lines.append("- Recent log:")
            lines.extend([f"  `{row}`" for row in git["recent_log"][:12]])

    for session in payload["relevant_sessions"]:
        lines.append("")
        lines.append(f"## {session['filename']}")
        lines.append("")
        lines.append(f"- Started: `{session['started_at']}`")
        lines.append(f"- Started ({payload['timezone']}): `{session['started_at_local']}`")
        lines.append(f"- CWD: `{session['cwd']}`")
        lines.append(f"- Match reason: `{session['match_reason']}`")
        lines.append(f"- Match confidence: `{session['match_confidence']}`")
        lines.append(
            "- Inventory reasons: "
            + ", ".join(f"`{reason}`" for reason in session["inventory_reasons"])
        )
        lines.append(f"- Transcript available: {'yes' if session['transcript_available'] else 'no'}")
        lines.append(f"- Sync source: `{session['sync_source']}`")
        lines.append(f"- Completeness: `{session['completeness_status']}`")
        lines.append(f"- Reason: {session['completeness_reason']}")
        lines.append(
            f"- Outcome: `{session['outcome']['status']}` ({session['outcome']['confidence']})"
        )
        lines.append(f"- Theme: `{session['theme']['key']}`")
        if session["outcome"]["evidence"]:
            lines.append(f"- Outcome evidence: {'; '.join(session['outcome']['evidence'])}")
        if session["priority_signals"]:
            lines.append(f"- Priority signals: {'; '.join(session['priority_signals'])}")
        if session["low_signal_operational"]:
            lines.append("- Low-signal operational thread: yes")
        if session["control_counts"]:
            controls = ", ".join(
                f"{kind}={count}" for kind, count in session["control_counts"].items()
            )
            lines.append(f"- Control message counts: {controls}")
        if session["assistant_tail"]:
            lines.append(f"- Assistant tail: {session['assistant_tail']}")
        lines.append("")
        lines.append("### User Messages")
        lines.append("")
        if session["user_messages"]:
            for index, message in enumerate(session["user_messages"], start=1):
                lines.append(f"{index}. {message['text']}")
        else:
            lines.append("_No recoverable user messages._")

    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    if args.format == "json":
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_markdown(payload))

    if payload["status"] == "incomplete" and not args.allow_incomplete:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
