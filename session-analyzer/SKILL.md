---
name: session-analyzer
description: >-
  Analyze Codex session logs for one repository, extract the repo-specific top-level
  conversations for a target day, summarize every user message in order, and surface
  the next best action. Use when the user asks what happened yesterday in a repo,
  which conversations touched a repo, what to work on next based on recent Codex
  work, or to reconstruct repo workstreams from session history.
---

# Session Analyzer

## Overview
Use this skill when the job is "figure out what happened in Codex sessions for repo X and synthesize the next move" rather than doing open-ended manual log spelunking.

The default path is: run the bundled Python sync+digest script once, read its compact digest, then only inspect raw transcripts or repo artifacts if the digest is complete and still leaves an ambiguity.

Default time selection is the previous calendar date in the user's locale timezone. If the user instead asks for a rolling recent window such as "last 6 hours" or "past 12 hours", pass `--last-hours N` and let the script own the window math.

The script now does more than enumerate sessions:
- inventories by target-day activity, not just thread creation day
- assigns repo-match confidence (`high`, `medium`, `low`)
- classifies each thread outcome heuristically (`implemented_and_merged`, `plan_only`, `blocked_waiting_for_input`, etc.)
- separates target-day historical evidence from current repo state
- emits ranked `candidate_next_actions` instead of forcing the final synthesis to start from a blank slate
- emits `theme_summaries` that collapse many sessions into one workstream-level truth, including current state, superseded earlier sessions, and landed-vs-local-only counts
- adds local-time timestamp fields alongside UTC so handoff reconstruction is easier in the user's timezone
- reports current-branch divergence from `main`/upstream when `--include-git` is enabled

## Quick Start
Run the extractor first.

```bash
python3 ~/.codex/skills/session-analyzer/scripts/repo_session_digest.py \
  --repo ~/TaskRally \
  --when yesterday \
  --format markdown \
  --include-git
```

If the user gave a specific date, replace `--when yesterday` with `--date YYYY-MM-DD`.

If the user asked for a recent rolling window instead of a calendar day:

```bash
python3 ~/.codex/skills/session-analyzer/scripts/repo_session_digest.py \
  --repo ~/TaskRally \
  --last-hours 6 \
  --format markdown \
  --include-git
```

If you want machine-readable output for follow-on processing:

```bash
python3 ~/.codex/skills/session-analyzer/scripts/repo_session_digest.py \
  --repo ~/TaskRally \
  --date 2026-03-31 \
  --format json \
  --include-git
```

The script now writes a canonical local mirror at
`~/.codex/sqlite/session_message_index.sqlite` by default.

Important: the script fails closed. If any relevant top-level repo thread cannot be fully recovered, it exits non-zero and prints `Status: INCOMPLETE`. In that case, do not synthesize a final "what should I work on next?" recommendation from the partial result.

Important: `--include-git` is now explicitly supplemental. It reports the repo's current state at digest time, not the target day's historical state. Use it to answer "what still appears local or unfinished now?", not "what definitely happened yesterday?"

When validating completeness, prefer a closed day such as `yesterday` after local midnight or an explicit historical date. An in-progress day can still be useful as a live format probe, and `--last-hours N` is useful for recent activity probes, but neither rolling windows nor in-progress days are as stable as a closed historical date for "all conversations recovered."

## Workflow

1. Resolve the repo path.
   - Prefer an absolute path when the user gives one.
   - If the user gives `~/repo`, let the script expand it.
   - The script matches the canonical repo path plus Codex worktrees that share the repo basename.
   - Generic basename-only matching is now disabled by default because it is lower confidence. Only enable it with `--allow-basename-fallback` when you explicitly want broader, noisier coverage.

2. Run the extractor before opening raw logs.
   - Use `--include-git` by default when the user wants "what should I do next" or "what landed vs not landed."
   - Use `--format markdown` unless you explicitly need JSON.
   - Use the default previous-calendar-date mode unless the user explicitly asks for a rolling recent window.
   - If the user says "last X hours" or "past X hours", pass `--last-hours X` instead of trying to convert that into `--date` or `--when`.
   - The extractor already:
     - inventories sessions by target-window activity instead of only thread creation time
     - excludes subagent-only sessions by default
     - matches repo cwd plus `.codex/worktrees/*/<repo-name>`
     - syncs relevant threads into the canonical local index
     - recovers user turns from rollout transcripts first
     - tries `logs_1.sqlite` request replay as a secondary recovery path
     - strips repeated `AGENTS.md` / environment wrappers
     - classifies non-user noise such as skill invocations and internal title-generation prompts
     - captures a short assistant tail for completion-state disambiguation when a transcript exists
     - classifies per-thread outcomes and candidate next actions heuristically
     - reports incomplete coverage instead of silently falling back

3. Read the digest and reconstruct workstreams.
   - Only do this if the digest status is `COMPLETE`.
   - Prefer ordered user requests over assistant confidence.
   - Treat `historical_evidence` and `candidate_next_actions` as the starting point for synthesis.
   - Treat repeated user focus across sessions as a strong priority signal.
   - Distinguish:
     - landed work
     - plan-only threads
     - PR-only threads
     - unresolved blockers
     - new issues discovered late in the day

4. Escalate to raw artifacts only when needed.
   - If the digest status is `INCOMPLETE`, escalate to recovery/debugging, not synthesis.
   - If the digest contains low-confidence repo matches, inspect those threads before letting them shape the final answer.
   - Open raw session files only if the digest leaves ambiguity about whether a thread ended in:
     - completed work
     - investigation only
     - recommendation only
     - blocked / unresolved
     - superseded by a later session
   - Cross-check repo state only after the session digest:
     - `git status --short`
     - `git log --oneline --decorate -n 20`
     - handover docs
     - `.agent/done` plans
   - When you do check repo state, keep the current-state evidence separate from historical evidence in your own write-up.

5. Answer decisively.
   - The default output shape for "what should I work on next?" should be:
     - top recommendation
     - why this is next
     - yesterday's workstreams
     - what seems done vs not done
     - other plausible next priorities
     - evidence
     - method check

## Default Heuristics

- Prefer the most recent unresolved high-leverage thread unless a more urgent blocker is explicit.
- Production failures, blocked deploys, failed release gates, and user-visible regressions outrank cleanup and roadmap work.
- Do not let current git state override the conversation evidence unless it clearly contradicts it.
- If later sessions obsolete earlier ones, say so explicitly.
- Count every top-level repo conversation you found, even if some contain only planning.
- Treat `implemented_local_only` as ambiguous: it often means work happened, but not necessarily that it landed.

## Script Notes

- The extractor assumes Codex data lives under `~/.codex` unless `CODEX_HOME` is set.
- It uses `state_5.sqlite` for thread inventory.
- It supports both calendar-day windows (`--when`, `--date`) and rolling recent windows (`--last-hours`).
- It uses rollout transcripts as the primary source of user-turn recovery.
- It searches all local rollout transcript roots that matter in this environment:
  - `~/.codex/sessions`
  - `~/.codex/archived_sessions`
  - `~/.codex/scripts/sessions`
- It uses `logs_1.sqlite` as a secondary recovery path when transcripts are missing.
- It writes the recovered threads/messages into `session_message_index.sqlite`.
- It reports per-thread completeness, sync source, and reason.
- It reports per-thread match confidence, inventory reasons, theme hints, and outcome classification.
- It does not silently trust `history.jsonl` or `first_user_message` as canonical coverage.
- If storage moves again, update the script's recovery logic instead of changing the workflow.

## JSON Output

The JSON payload now has a stable top-level `schema_version`.

Key top-level fields:
- `status`: overall digest completeness (`complete` or `incomplete`)
- `target_mode`: `calendar_day` or `rolling_hours`
- `target_window`: normalized window metadata with `label`, `start_at`, `end_at`, and optional `last_hours`
- `relevant_sessions`: ordered list of repo-relevant top-level sessions
- `historical_evidence`: aggregate counts derived from target-day session evidence
- `candidate_next_actions`: ranked unresolved follow-up candidates derived from the sessions
- `theme_summaries`: workstream rollups with a `current_state`, supporting session chronology, and superseded-session hints
- `current_repo_state`: optional current-state snapshot, only present when `--include-git` is used

Each `relevant_sessions[]` entry includes:
- `match_reason`: why the repo matched (`cwd_within_repo`, `codex_worktree_name_match`, or low-confidence `cwd_basename_match`)
- `match_confidence`: `high`, `medium`, or `low`
- `inventory_reasons`: why the session was included for the target day (`created_on_day`, `state_updated_on_day`, `transcript_activity_on_day`, `log_activity_on_day`)
- `started_at_local`: local-time mirror of `started_at`
- `user_messages`: array of `{ordinal, kind, text, source, turn_id}`
- `outcome`: `{status, confidence, evidence[]}` heuristic thread classification
- `theme`: `{key, title}` lightweight workstream grouping hint
- `priority_signals`: repeated urgency / verification / "what next?" hints that should shape synthesis
- `low_signal_operational`: true for housekeeping threads like plain pulls that should usually not become top recommendations

Minimal example:

```json
{
  "schema_version": 2,
  "status": "complete",
  "target_mode": "rolling_hours",
  "target_window": {
    "mode": "rolling_hours",
    "label": "last 6 hours",
    "start_at": "2026-04-01T12:00:00Z",
    "end_at": "2026-04-01T18:00:00Z",
    "timezone": "America/Los_Angeles",
    "last_hours": 6
  },
  "relevant_sessions": [
    {
      "session_id": "thread-id",
      "match_reason": "cwd_within_repo",
      "match_confidence": "high",
      "inventory_reasons": ["created_on_day", "transcript_activity_on_day"],
      "user_messages": [
        {
          "ordinal": 1,
          "kind": "user_request",
          "text": "find the root cause",
          "source": "rollout",
          "turn_id": null
        }
      ],
      "outcome": {
        "status": "investigation_only",
        "confidence": "medium",
        "evidence": ["thread emphasizes investigation/root-cause analysis without landing work"]
      },
      "theme": {
        "key": "release_rollout",
        "title": "Repair the rollout and hosted release-proof path"
      }
    }
  ],
  "candidate_next_actions": [
    {
      "theme_key": "release_rollout",
      "title": "Repair the rollout and hosted release-proof path",
      "score": 91
    }
  ],
  "current_repo_state": {
    "git": {
      "note": "This is the current repo state at digest time..."
    }
  }
}
```

## When To Inspect More

- The digest says a thread ended with a handover doc, but the handover mentions a blocker you need to verify.
- Two sessions appear to be continuations of the same thread and you need chronology to decide which supersedes which.
- The user explicitly asks for exact quotes or direct evidence from a session.
- Repo state suggests something landed, but the session digest suggests it stayed blocked.
- A low-confidence basename match is surfacing high-leverage conclusions.
- The top-ranked `candidate_next_actions` disagree with the repo handover or `.agent/done` docs.
- The user asked for a rolling recent window and you need a stable historical benchmark instead; switch to an explicit `--date` if completeness matters more than recency.

## scripts/

`repo_session_digest.py`
- Primary entrypoint for repo-scoped session analysis.
- Syncs relevant threads into the canonical local mirror, then emits a digest.
- Exits non-zero when any relevant thread remains incomplete.
