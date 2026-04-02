---
name: tool-error-analyzer
description: >-
  Analyze Codex rollout transcripts for one repository and time window, extract
  repo-scoped tool calls that failed, cluster repeated error patterns, and
  recommend the next agent/tooling improvements. Use when the user wants to
  inspect tool-call failures, operational friction, repeated command mistakes,
  patch failures, or prompt/tooling improvements based on recent Codex runs.
---

# Tool Error Analyzer

## Overview
Use this skill when the job is "show me where the agent struggled operationally"
rather than "summarize what work happened."

The default path is: run the bundled digest script once, read its clustered
failure summary, and only open raw rollout transcripts if the digest reports
incomplete coverage or a cluster needs deeper inspection.

This skill is transcript-first. It reads real rollout JSONL files and pairs:
- `function_call` with `function_call_output`
- `custom_tool_call` with `custom_tool_call_output`

The script focuses on meaningful failures such as:
- shell commands that exited non-zero with real errors
- wrong cwd or wrong path assumptions
- shell quoting and globbing mistakes
- validation commands that failed
- `apply_patch` verification failures

It intentionally filters low-signal cases such as plain `rg` no-match exits when
the transcript shows no actual error text.

## Quick Start
Run the digest first.

```bash
python3 ~/.codex/skills/tool-error-analyzer/scripts/repo_tool_error_digest.py \
  --repo ~/TaskRally \
  --when yesterday \
  --format markdown
```

If the user gave a specific date, replace `--when yesterday` with
`--date YYYY-MM-DD`.

If the user asked for a rolling recent window:

```bash
python3 ~/.codex/skills/tool-error-analyzer/scripts/repo_tool_error_digest.py \
  --repo ~/TaskRally \
  --last-hours 6 \
  --format markdown
```

If you want machine-readable output:

```bash
python3 ~/.codex/skills/tool-error-analyzer/scripts/repo_tool_error_digest.py \
  --repo ~/TaskRally \
  --date 2026-04-01 \
  --format json
```

Important: the script is fail-closed for transcript coverage. If any relevant
repo session for the target window has no readable rollout transcript, the
digest reports `INCOMPLETE` and exits non-zero unless `--allow-incomplete` is
set. Do not make confident process recommendations from a partial result.

## Workflow

1. Resolve the repo path.
   - Prefer an absolute path when the user gives one.
   - If the user gives `~/repo`, let the script expand it.
   - The script matches the canonical repo path plus Codex worktrees that share
     the repo basename.
   - Basename-only fallback is disabled by default because it is lower
     confidence.

2. Run the digest before reading raw transcripts.
   - Use `--format markdown` unless you explicitly need JSON.
   - Use the default previous-calendar-date mode unless the user explicitly asks
     for a rolling recent window.
   - If the user says "last X hours" or "past X hours", pass `--last-hours X`.
   - Keep subagents excluded unless you explicitly want them.

3. Read the clustered failure summary.
   - Treat `candidate_improvements` as the default starting point.
   - Separate repeated recoverable friction from unresolved failures.
   - Pay attention to whether failures were later recovered in the same session.

4. Escalate to raw transcripts only when needed.
   - If the digest is incomplete, debug coverage first.
   - If a cluster is ambiguous, inspect one representative transcript.
   - Open raw transcripts when you need to verify:
     - whether a failure was benign
     - whether the retry really fixed the issue
     - whether a validation failure remained unresolved

5. Answer in terms of agent improvement.
   - The default output shape for "what should we improve next?" should be:
     - top recurring failure pattern
     - why it matters
     - whether it was usually recovered
     - concrete workflow or prompt/tooling adjustment
     - representative evidence

## Default Heuristics

- Prefer unresolved repeated failures over one-off recoverable hiccups.
- Treat `apply_patch verification failed` as a real workflow smell even when a
  later patch succeeds.
- Treat shell quoting mistakes and wrong-path commands as prompt/workflow issues,
  not product bugs.
- Filter out plain `rg`/`grep` no-match exits when there is no other error text.
- Treat missing transcripts as incomplete coverage rather than silently skipping
  the session.

## Script Notes

- The script assumes Codex data lives under `~/.codex` unless `CODEX_HOME` is
  set.
- It reuses the same repo/time-window session inventory logic as
  `session-analyzer`.
- It reads rollout transcripts from:
  - `~/.codex/sessions`
  - `~/.codex/archived_sessions`
  - `~/.codex/scripts/sessions`
- It does not rely on `logs_1.sqlite` for tool error extraction.
- It pairs tool calls and outputs by `call_id`.
- It detects recovery heuristically from later successful calls in the same
  session.

## JSON Output

The JSON payload has a stable top-level `schema_version`.

Key top-level fields:
- `status`: overall digest completeness (`complete` or `incomplete`)
- `target_mode`: `calendar_day` or `rolling_hours`
- `target_window`: normalized window metadata
- `relevant_sessions`: repo-relevant top-level sessions with per-session failure
  counts
- `tool_error_events`: normalized meaningful failures
- `error_clusters`: grouped recurring failure patterns
- `candidate_improvements`: ranked next improvements derived from clusters

Each `tool_error_events[]` entry includes:
- `session_id`
- `timestamp`
- `tool_name`
- `tool_family`
- `input_summary`
- `error_kind`
- `error_family`
- `exit_code`
- `recovered_later`
- `recovery_call_id`
- `target_hints`

Minimal example:

```json
{
  "schema_version": 1,
  "status": "complete",
  "target_mode": "rolling_hours",
  "tool_error_events": [
    {
      "session_id": "thread-id",
      "tool_name": "exec_command",
      "tool_family": "function",
      "error_kind": "shell_globbing",
      "error_family": "agent_command_bug",
      "exit_code": 1,
      "recovered_later": true
    }
  ],
  "candidate_improvements": [
    {
      "cluster_key": "shell_globbing",
      "title": "Quote shell paths before opening files with glob characters",
      "score": 12
    }
  ]
}
```
