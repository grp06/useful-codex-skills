#!/usr/bin/env python3
"""Summarize repo-scoped tool-call failures from Codex rollout transcripts."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


SCHEMA_VERSION = 1

EXIT_CODE_RE = re.compile(r"Process exited with code (\d+)")
PATCH_FILE_RE = re.compile(r"^\*\*\* (?:Update|Add|Delete) File: (.+)$", re.MULTILINE)
PATH_TOKEN_RE = re.compile(r"(?<![\w.-])(?:/[^ \n\t\"']+|[A-Za-z0-9_./-]+\.[A-Za-z0-9_./-]+)")

VALIDATION_MARKERS = (
    " test",
    "pytest",
    "vitest",
    "jest",
    "go test",
    "cargo test",
    "npm run test",
    "pnpm test",
    "yarn test",
    "ruff",
    "eslint",
    "tsc",
    "mypy",
    "typecheck",
    "lint",
    " build",
    "check",
)

ERROR_HELP = {
    "patch_verification_failed": {
        "title": "Re-read target files before patching when context may have shifted",
        "recommendation": (
            "When an edit fails to apply, refresh the file contents first and rebuild the patch "
            "from current context instead of retrying the stale hunk."
        ),
    },
    "shell_globbing": {
        "title": "Quote shell paths before opening files with glob characters",
        "recommendation": (
            "Wrap bracketed or wildcard-like paths in quotes before using shell tools such as "
            "`sed`, `cat`, or `rg`."
        ),
    },
    "wrong_path_or_cwd": {
        "title": "Verify cwd and repo-relative paths before running file or git commands",
        "recommendation": (
            "Probe the working tree shape before assuming a path or repo root exists in the "
            "current session."
        ),
    },
    "validation_failure": {
        "title": "Treat failing validation commands as first-class follow-up work",
        "recommendation": (
            "When tests, builds, or lint checks fail, capture the root cause and resolve or "
            "explicitly hand off the failure instead of letting it blend into general tool noise."
        ),
    },
    "missing_command": {
        "title": "Probe command availability before assuming local tooling exists",
        "recommendation": (
            "Check whether repo-local commands and CLIs exist before leaning on them in a flow "
            "that depends on deterministic tooling."
        ),
    },
    "permission_denied": {
        "title": "Handle execute-permission failures explicitly",
        "recommendation": (
            "When a script is not executable, either invoke it through the right interpreter or "
            "fix the execute bit before retrying."
        ),
    },
    "unknown_tool_failure": {
        "title": "Review uncategorized tool failures and tighten the classifier",
        "recommendation": (
            "This cluster did not fit a sharper bucket. Inspect representative examples and add a "
            "more specific rule if the pattern repeats."
        ),
    },
}

ERROR_PRIORITY = {
    "patch_verification_failed": 2,
    "validation_failure": 1,
}


def load_session_analyzer_module():
    script_path = (
        Path(__file__).resolve().parents[2]
        / "session-analyzer"
        / "scripts"
        / "repo_session_digest.py"
    )
    if not script_path.exists():
        raise RuntimeError(f"session-analyzer script not found at {script_path}")
    spec = importlib.util.spec_from_file_location("session_analyzer_repo_digest", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load session-analyzer module from {script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SESSION_ANALYZER = load_session_analyzer_module()


@dataclass
class PendingCall:
    call_id: str
    timestamp: str | None
    order: int
    tool_family: str
    tool_name: str
    raw_input: str
    input_summary: str
    target_hints: list[str]
    command_stem: str | None


@dataclass
class ToolEvent:
    session_id: str
    timestamp: str | None
    order: int
    call_id: str
    tool_family: str
    tool_name: str
    raw_input: str
    input_summary: str
    raw_output: str
    target_hints: list[str]
    command_stem: str | None
    success: bool
    meaningful_failure: bool
    exit_code: int | None
    error_kind: str | None
    error_family: str | None
    error_excerpt: str
    recovered_later: bool = False
    recovery_call_id: str | None = None
    recovery_reason: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract repo-scoped tool-call failures from Codex rollout transcripts for one "
            "calendar day or rolling time window."
        )
    )
    parser.add_argument("--repo", required=True, help="Repo path, e.g. ~/TaskRally")
    time_group = parser.add_mutually_exclusive_group()
    time_group.add_argument(
        "--when",
        choices=["today", "yesterday"],
        help="Relative day shortcut. Defaults to `yesterday` when unset.",
    )
    time_group.add_argument("--date", help="Absolute calendar date in YYYY-MM-DD")
    time_group.add_argument(
        "--last-hours",
        type=float,
        help="Rolling lookback window ending now, for example `--last-hours 6`.",
    )
    parser.add_argument(
        "--timezone",
        default=str(getattr(SESSION_ANALYZER, "os").environ.get("TZ", "America/Los_Angeles")),
        help="IANA timezone used for relative dates.",
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format.",
    )
    parser.add_argument(
        "--include-subagents",
        action="store_true",
        help="Include subagent sessions. Off by default.",
    )
    parser.add_argument(
        "--allow-basename-fallback",
        action="store_true",
        help="Allow lower-confidence cwd basename matches outside the repo boundary.",
    )
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Emit a best-effort digest even when some relevant transcripts are missing.",
    )
    return parser.parse_args()


def collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_event_timestamp(raw: str | None):
    return SESSION_ANALYZER.parse_event_timestamp(raw)


def iso_local_from_utc(raw: str | None, timezone_name: str) -> str | None:
    return SESSION_ANALYZER.iso_local_from_utc(raw, timezone_name)


def extract_command_stem(command: str) -> str | None:
    text = command.strip()
    if not text:
        return None
    if text.startswith("python3 - <<'PY'") or text.startswith('python3 - <<"PY"'):
        return "python3"
    parts = text.split()
    return parts[0] if parts else None


def extract_target_hints(text: str) -> list[str]:
    hints: list[str] = []
    for match in PATH_TOKEN_RE.findall(text or ""):
        cleaned = match.strip("\"'")
        name = Path(cleaned).name
        if name:
            hints.append(name)
    seen: set[str] = set()
    ordered: list[str] = []
    for hint in hints:
        if hint in seen:
            continue
        seen.add(hint)
        ordered.append(hint)
    return ordered[:6]


def summarize_function_input(tool_name: str, raw_arguments: str) -> tuple[str, list[str], str | None]:
    summary = raw_arguments
    target_hints: list[str] = []
    command_stem: str | None = None
    try:
        payload = json.loads(raw_arguments)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        if tool_name == "exec_command":
            summary = str(payload.get("cmd", "")).strip() or raw_arguments
            target_hints = extract_target_hints(summary)
            command_stem = extract_command_stem(summary)
        else:
            compact = json.dumps(payload, sort_keys=True)
            summary = compact[:220]
            target_hints = extract_target_hints(compact)
            command_stem = tool_name
    else:
        summary = raw_arguments[:220]
        target_hints = extract_target_hints(raw_arguments)
        command_stem = tool_name
    return summary, target_hints, command_stem


def summarize_custom_input(tool_name: str, raw_input: str) -> tuple[str, list[str], str | None]:
    if tool_name == "apply_patch":
        files = [Path(path).name for path in PATCH_FILE_RE.findall(raw_input)]
        file_summary = ", ".join(files[:3]) if files else "unknown target"
        summary = f"apply_patch: {file_summary}"
        return summary, files[:6], "apply_patch"
    return collapse_ws(raw_input)[:220], extract_target_hints(raw_input), tool_name


def parse_terminal_output_body(output: str) -> str:
    idx = output.find("Output:")
    if idx == -1:
        return output.strip()
    return output[idx + len("Output:") :].strip()


def parse_exit_code(output: str) -> int | None:
    match = EXIT_CODE_RE.search(output or "")
    if not match:
        return None
    return int(match.group(1))


def extract_error_excerpt(output: str) -> str:
    body = parse_terminal_output_body(output)
    text = body or output
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return collapse_ws(" | ".join(lines[:3]))[:320]


def is_expected_search_miss(command_stem: str | None, output: str, exit_code: int | None) -> bool:
    if command_stem not in {"rg", "grep"} or exit_code != 1:
        return False
    lower = output.lower()
    if any(
        marker in lower
        for marker in (
            "os error",
            "no such file or directory",
            "permission denied",
            "command not found",
            "error:",
            "invalid",
            "not a git repository",
        )
    ):
        return False
    return parse_terminal_output_body(output) == ""


def classify_exec_failure(command: str, output: str, exit_code: int | None) -> tuple[bool, str | None, str | None]:
    if exit_code in (None, 0):
        return False, None, None
    command_stem = extract_command_stem(command)
    lower = output.lower()
    if is_expected_search_miss(command_stem, output, exit_code):
        return False, None, None
    if "no matches found:" in lower:
        return True, "shell_globbing", "agent_command_bug"
    if "permission denied" in lower:
        return True, "permission_denied", "environment_mismatch"
    if "command not found" in lower:
        return True, "missing_command", "environment_mismatch"
    if any(
        marker in lower
        for marker in (
            "no such file or directory",
            "not a git repository",
            "does not exist",
            "cannot stat",
            "unable to access",
        )
    ):
        return True, "wrong_path_or_cwd", "environment_mismatch"
    lowered_command = f" {command.lower()} "
    if " gh run watch " in lowered_command:
        return True, "validation_failure", "validation_failure"
    if command_stem == "node" and any(
        marker in lower
        for marker in ("typeerror:", "referenceerror:", "syntaxerror:", "error:")
    ):
        return True, "validation_failure", "validation_failure"
    if any(marker in lowered_command for marker in VALIDATION_MARKERS):
        return True, "validation_failure", "validation_failure"
    return True, "unknown_tool_failure", "tooling_failure"


def parse_custom_output(output: str) -> tuple[str, int | None]:
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return output, None
    if not isinstance(payload, dict):
        return output, None
    inner = str(payload.get("output", output))
    metadata = payload.get("metadata")
    exit_code = None
    if isinstance(metadata, dict):
        raw_exit = metadata.get("exit_code")
        if isinstance(raw_exit, int):
            exit_code = raw_exit
    return inner, exit_code


def classify_custom_failure(tool_name: str, output: str, exit_code: int | None) -> tuple[bool, str | None, str | None]:
    lower = output.lower()
    if "apply_patch verification failed" in lower:
        return True, "patch_verification_failed", "edit_application_failure"
    if exit_code in (None, 0) and not any(marker in lower for marker in ("failed", "error")):
        return False, None, None
    if exit_code == 0:
        return False, None, None
    return True, "unknown_tool_failure", "tooling_failure"


def parse_tool_events(transcript_path: str, session_id: str) -> list[ToolEvent]:
    events: list[ToolEvent] = []
    pending: dict[str, PendingCall] = {}
    order = 0
    with Path(transcript_path).open() as handle:
        for raw_line in handle:
            try:
                item = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            if item.get("type") != "response_item":
                continue
            payload = item.get("payload", {})
            if not isinstance(payload, dict):
                continue
            payload_type = payload.get("type")
            if payload_type == "function_call":
                call_id = payload.get("call_id")
                tool_name = str(payload.get("name") or "")
                if not call_id or not tool_name:
                    continue
                order += 1
                raw_arguments = str(payload.get("arguments") or "")
                summary, target_hints, command_stem = summarize_function_input(
                    tool_name, raw_arguments
                )
                pending[call_id] = PendingCall(
                    call_id=call_id,
                    timestamp=item.get("timestamp"),
                    order=order,
                    tool_family="function",
                    tool_name=tool_name,
                    raw_input=raw_arguments,
                    input_summary=summary,
                    target_hints=target_hints,
                    command_stem=command_stem,
                )
                continue
            if payload_type == "custom_tool_call":
                call_id = payload.get("call_id")
                tool_name = str(payload.get("name") or "")
                if not call_id or not tool_name:
                    continue
                order += 1
                raw_input = str(payload.get("input") or "")
                summary, target_hints, command_stem = summarize_custom_input(tool_name, raw_input)
                pending[call_id] = PendingCall(
                    call_id=call_id,
                    timestamp=item.get("timestamp"),
                    order=order,
                    tool_family="custom",
                    tool_name=tool_name,
                    raw_input=raw_input,
                    input_summary=summary,
                    target_hints=target_hints,
                    command_stem=command_stem,
                )
                continue
            if payload_type not in {"function_call_output", "custom_tool_call_output"}:
                continue
            call_id = payload.get("call_id")
            if not call_id or call_id not in pending:
                continue
            call = pending.pop(call_id)
            raw_output = str(payload.get("output") or "")
            exit_code = parse_exit_code(raw_output)
            output_for_classification = raw_output
            if call.tool_family == "custom":
                output_for_classification, custom_exit = parse_custom_output(raw_output)
                if exit_code is None:
                    exit_code = custom_exit
                meaningful_failure, error_kind, error_family = classify_custom_failure(
                    call.tool_name, output_for_classification, exit_code
                )
            else:
                meaningful_failure, error_kind, error_family = classify_exec_failure(
                    call.input_summary, raw_output, exit_code
                )
            success = not meaningful_failure
            events.append(
                ToolEvent(
                    session_id=session_id,
                    timestamp=item.get("timestamp") or call.timestamp,
                    order=call.order,
                    call_id=call.call_id,
                    tool_family=call.tool_family,
                    tool_name=call.tool_name,
                    raw_input=call.raw_input,
                    input_summary=call.input_summary,
                    raw_output=output_for_classification,
                    target_hints=call.target_hints,
                    command_stem=call.command_stem,
                    success=success,
                    meaningful_failure=meaningful_failure,
                    exit_code=exit_code,
                    error_kind=error_kind,
                    error_family=error_family,
                    error_excerpt=extract_error_excerpt(output_for_classification),
                )
            )
    events.sort(key=lambda item: (item.timestamp or "", item.order, item.call_id))
    return events


def shares_target_hint(left: ToolEvent, right: ToolEvent) -> bool:
    if not left.target_hints or not right.target_hints:
        return False
    return bool(set(left.target_hints) & set(right.target_hints))


def detect_recoveries(events: list[ToolEvent]) -> None:
    for index, event in enumerate(events):
        if not event.meaningful_failure:
            continue
        for later in events[index + 1 : index + 7]:
            if later.meaningful_failure:
                continue
            if event.tool_name != later.tool_name:
                continue
            if event.command_stem and later.command_stem and event.command_stem == later.command_stem:
                if shares_target_hint(event, later) or not event.target_hints:
                    event.recovered_later = True
                    event.recovery_call_id = later.call_id
                    event.recovery_reason = "later success with matching tool and command stem"
                    break
            if shares_target_hint(event, later):
                event.recovered_later = True
                event.recovery_call_id = later.call_id
                event.recovery_reason = "later success touched the same target hint"
                break


def normalize_event(event: ToolEvent) -> dict:
    return {
        "session_id": event.session_id,
        "timestamp": event.timestamp,
        "timestamp_local": iso_local_from_utc(event.timestamp, args_timezone_cache.get("timezone")),
        "call_id": event.call_id,
        "tool_family": event.tool_family,
        "tool_name": event.tool_name,
        "input_summary": event.input_summary,
        "exit_code": event.exit_code,
        "error_kind": event.error_kind,
        "error_family": event.error_family,
        "error_excerpt": event.error_excerpt,
        "target_hints": event.target_hints,
        "recovered_later": event.recovered_later,
        "recovery_call_id": event.recovery_call_id,
        "recovery_reason": event.recovery_reason,
    }


def build_error_clusters(events: list[ToolEvent]) -> list[dict]:
    grouped: dict[str, list[ToolEvent]] = defaultdict(list)
    for event in events:
        if not event.meaningful_failure or not event.error_kind:
            continue
        grouped[event.error_kind].append(event)

    clusters: list[dict] = []
    for key, items in grouped.items():
        info = ERROR_HELP.get(key, ERROR_HELP["unknown_tool_failure"])
        session_ids = sorted({item.session_id for item in items})
        recovered_count = sum(1 for item in items if item.recovered_later)
        unresolved_count = len(items) - recovered_count
        score = (
            unresolved_count * 10
            + len(session_ids) * 2
            + ERROR_PRIORITY.get(key, 0)
            - recovered_count * 2
        )
        samples = [
            {
                "session_id": item.session_id,
                "timestamp": item.timestamp,
                "tool_name": item.tool_name,
                "input_summary": item.input_summary,
                "error_excerpt": item.error_excerpt,
                "recovered_later": item.recovered_later,
            }
            for item in items[:3]
        ]
        clusters.append(
            {
                "cluster_key": key,
                "title": info["title"],
                "recommendation": info["recommendation"],
                "error_family": items[0].error_family,
                "count": len(items),
                "session_count": len(session_ids),
                "recovered_count": recovered_count,
                "unresolved_count": unresolved_count,
                "score": score,
                "sample_events": samples,
            }
        )
    clusters.sort(key=lambda item: (item["score"], item["unresolved_count"], item["count"]), reverse=True)
    return clusters


def build_payload(args: argparse.Namespace) -> dict:
    args_timezone_cache["timezone"] = args.timezone
    window = SESSION_ANALYZER.resolve_time_window(args)
    home = SESSION_ANALYZER.codex_home()
    repo_canon, repo_name = SESSION_ANALYZER.repo_matcher(args.repo)
    inventory = SESSION_ANALYZER.inventory_sessions_from_state(
        home=home,
        window=window,
        repo_canon=repo_canon,
        repo_name=repo_name,
        include_subagents=args.include_subagents,
        allow_basename_fallback=args.allow_basename_fallback,
    )

    incomplete_sessions: list[dict] = []
    relevant_sessions: list[dict] = []
    all_failures: list[ToolEvent] = []

    for item in inventory:
        if not item.transcript_path or not Path(item.transcript_path).exists():
            incomplete_sessions.append(
                {
                    "session_id": item.thread_id,
                    "filename": Path(item.rollout_path).name,
                    "started_at": item.started_at,
                    "cwd": item.cwd,
                    "reason": "readable rollout transcript missing",
                }
            )
            relevant_sessions.append(
                {
                    "session_id": item.thread_id,
                    "filename": Path(item.rollout_path).name,
                    "path": item.rollout_path,
                    "transcript_path": item.transcript_path,
                    "started_at": item.started_at,
                    "started_at_local": iso_local_from_utc(item.started_at, args.timezone),
                    "cwd": item.cwd,
                    "match_reason": item.match_reason,
                    "match_confidence": item.match_confidence,
                    "inventory_reasons": item.inventory_reasons,
                    "transcript_available": False,
                    "completeness_status": "incomplete",
                    "completeness_reason": "readable rollout transcript missing",
                    "tool_event_count": 0,
                    "meaningful_failure_count": 0,
                    "recovered_failure_count": 0,
                    "unrecovered_failure_count": 0,
                    "failure_counts": {},
                    "top_failures": [],
                }
            )
            continue

        events = parse_tool_events(item.transcript_path, item.thread_id)
        detect_recoveries(events)
        failures = [event for event in events if event.meaningful_failure]
        all_failures.extend(failures)

        failure_counts: Counter[str] = Counter(
            event.error_kind for event in failures if event.error_kind
        )
        relevant_sessions.append(
            {
                "session_id": item.thread_id,
                "filename": Path(item.rollout_path).name,
                "path": item.rollout_path,
                "transcript_path": item.transcript_path,
                "started_at": item.started_at,
                "started_at_local": iso_local_from_utc(item.started_at, args.timezone),
                "cwd": item.cwd,
                "match_reason": item.match_reason,
                "match_confidence": item.match_confidence,
                "inventory_reasons": item.inventory_reasons,
                "transcript_available": True,
                "completeness_status": "complete",
                "completeness_reason": "rollout transcript parsed for tool events",
                "tool_event_count": len(events),
                "meaningful_failure_count": len(failures),
                "recovered_failure_count": sum(1 for event in failures if event.recovered_later),
                "unrecovered_failure_count": sum(1 for event in failures if not event.recovered_later),
                "failure_counts": dict(sorted(failure_counts.items())),
                "top_failures": [normalize_event(event) for event in failures[:5]],
            }
        )

    relevant_sessions.sort(key=lambda item: (item["started_at"], item["filename"]))
    incomplete_sessions.sort(key=lambda item: (item["started_at"], item["filename"]))
    clusters = build_error_clusters(all_failures)
    candidate_improvements = [
        {
            "cluster_key": cluster["cluster_key"],
            "title": cluster["title"],
            "score": cluster["score"],
            "recommendation": cluster["recommendation"],
            "count": cluster["count"],
            "unresolved_count": cluster["unresolved_count"],
            "session_count": cluster["session_count"],
        }
        for cluster in clusters
    ]

    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "complete" if not incomplete_sessions else "incomplete",
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
            "start_at_local": window.start_utc.astimezone(
                SESSION_ANALYZER.timezone_info(args.timezone)
            ).isoformat(),
            "end_at": window.end_utc.isoformat().replace("+00:00", "Z"),
            "end_at_local": window.end_utc.astimezone(
                SESSION_ANALYZER.timezone_info(args.timezone)
            ).isoformat(),
            "timezone": window.timezone,
            "last_hours": window.last_hours,
        },
        "timezone": args.timezone,
        "codex_home": str(home),
        "session_inventory_count": len(inventory),
        "relevant_sessions": relevant_sessions,
        "tool_error_events": [normalize_event(event) for event in all_failures],
        "error_clusters": clusters,
        "candidate_improvements": candidate_improvements,
        "incomplete_sessions": incomplete_sessions,
        "totals": {
            "relevant_session_count": len(relevant_sessions),
            "complete_session_count": len(relevant_sessions) - len(incomplete_sessions),
            "incomplete_session_count": len(incomplete_sessions),
            "tool_error_count": len(all_failures),
            "recovered_tool_error_count": sum(1 for event in all_failures if event.recovered_later),
            "unrecovered_tool_error_count": sum(
                1 for event in all_failures if not event.recovered_later
            ),
            "cluster_count": len(clusters),
        },
    }
    return payload


def render_markdown(payload: dict) -> str:
    window = payload["target_window"]
    lines = [
        "# Repo Tool Error Digest",
        "",
        f"- Schema version: `{payload['schema_version']}`",
        f"- Status: `{payload['status'].upper()}`",
        f"- Repo: `{payload['repo']['input']}`",
        f"- Canonical path: `{payload['repo']['canonical_path']}`",
    ]
    if payload["target_mode"] == "calendar_day":
        lines.append(f"- Target date: `{payload['target_date']}`")
    else:
        lines.append(f"- Target window: `{window['label']}`")
    lines.extend(
        [
            f"- Window start: `{window['start_at']}`",
            f"- Window start ({window['timezone']}): `{window['start_at_local']}`",
            f"- Window end: `{window['end_at']}`",
            f"- Window end ({window['timezone']}): `{window['end_at_local']}`",
            f"- Matching top-level threads inventoried: {payload['session_inventory_count']}",
            f"- Relevant top-level sessions: {payload['totals']['relevant_session_count']}",
            f"- Meaningful tool failures: {payload['totals']['tool_error_count']}",
            f"- Recovered failures: {payload['totals']['recovered_tool_error_count']}",
            f"- Unrecovered failures: {payload['totals']['unrecovered_tool_error_count']}",
            f"- Error clusters: {payload['totals']['cluster_count']}",
        ]
    )

    if payload["candidate_improvements"]:
        lines.extend(["", "## Candidate Improvements", ""])
        for index, item in enumerate(payload["candidate_improvements"], start=1):
            lines.append(f"{index}. {item['title']} (score {item['score']})")
            lines.append(f"   Recommendation: {item['recommendation']}")
            lines.append(
                f"   Evidence: failures={item['count']}, unresolved={item['unresolved_count']}, sessions={item['session_count']}"
            )

    if payload["error_clusters"]:
        lines.extend(["", "## Error Clusters", ""])
        for cluster in payload["error_clusters"]:
            lines.append(
                f"- `{cluster['cluster_key']}`: {cluster['title']} "
                f"(count={cluster['count']}, unresolved={cluster['unresolved_count']}, recovered={cluster['recovered_count']})"
            )
            lines.append(f"  recommendation: {cluster['recommendation']}")
            for sample in cluster["sample_events"]:
                lines.append(
                    f"  sample: `{sample['tool_name']}` {sample['input_summary']} -> {sample['error_excerpt']}"
                )

    if payload["incomplete_sessions"]:
        lines.extend(["", "## Incomplete Sessions", ""])
        lines.append(
            "The digest is incomplete. Do not make high-confidence process recommendations from this result unless you explicitly allow incomplete coverage."
        )
        lines.append("")
        for item in payload["incomplete_sessions"]:
            lines.append(f"- `{item['filename']}` `{item['started_at']}`")
            lines.append(f"  reason: {item['reason']}")

    for session in payload["relevant_sessions"]:
        lines.extend(["", f"## {session['filename']}", ""])
        lines.extend(
            [
                f"- Started: `{session['started_at']}`",
                f"- Started ({payload['timezone']}): `{session['started_at_local']}`",
                f"- CWD: `{session['cwd']}`",
                f"- Match confidence: `{session['match_confidence']}`",
                "- Inventory reasons: "
                + ", ".join(f"`{reason}`" for reason in session["inventory_reasons"]),
                f"- Transcript available: {'yes' if session['transcript_available'] else 'no'}",
                f"- Completeness: `{session['completeness_status']}`",
                f"- Reason: {session['completeness_reason']}",
                f"- Tool events parsed: {session['tool_event_count']}",
                f"- Meaningful failures: {session['meaningful_failure_count']}",
                f"- Recovered failures: {session['recovered_failure_count']}",
                f"- Unrecovered failures: {session['unrecovered_failure_count']}",
            ]
        )
        if session["failure_counts"]:
            lines.append(
                "- Failure counts: "
                + ", ".join(f"`{kind}`={count}" for kind, count in session["failure_counts"].items())
            )
        if session["top_failures"]:
            lines.append("")
            lines.append("### Top Failures")
            lines.append("")
            for index, event in enumerate(session["top_failures"], start=1):
                recovered = "recovered" if event["recovered_later"] else "unrecovered"
                lines.append(
                    f"{index}. `{event['error_kind']}` via `{event['tool_name']}` ({recovered})"
                )
                lines.append(f"   command: {event['input_summary']}")
                lines.append(f"   excerpt: {event['error_excerpt']}")
        else:
            lines.append("- No meaningful tool failures in this session.")
    return "\n".join(lines) + "\n"


args_timezone_cache = {"timezone": "America/Los_Angeles"}


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
