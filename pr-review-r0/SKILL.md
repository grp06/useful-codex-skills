---
name: pr-review-r0
description: >-
  Triage open PRs: identify and close junk, slop, or irrelevant PRs.
  Use when cleaning up PR backlog or filtering out low-quality PRs.
---

HARD REQUIREMENT: You MUST spawn subagents in Phase 2. Do NOT evaluate PRs sequentially yourself. If you have suspect PRs and cannot spawn subagents, STOP and reply: "BLOCKED: could not spawn subagents".

PHASE 1: Title scan (quick filter)

Fetch first 100 open PRs with titles only:

```sh
gh pr list --state open --json number,title,author,createdAt --limit 100
```

Scan titles for suspect signals:
- Vague/generic titles ("fix", "update", "changes", "WIP", "test")
- Auto-generated titles ("Bump X from Y to Z" if not a bot account)
- Very old PRs (created 60+ days ago)
- Titles that don't describe a clear change

Output a list of suspect PR numbers. Only these move to Phase 2.

PHASE 2: Deep evaluation (parallel subagents required)

Split suspect PRs into batches and spawn up to 4 subagents (one per batch). Do NOT evaluate sequentially.

Each subagent receives a batch of PR numbers and must:
1. Fetch full PR details: `gh pr view <number> --json body,comments,commits,reviews,files`
2. Evaluate against junk criteria below
3. Return list of PRs to close with reason (Stale, Duplicate, Out of scope, Abandoned, or Superseded)

Wait for all subagents to complete.

Junk criteria:
- Stale (no activity for 60+ days)
- Vague/meaningless title or description
- Duplicate of another PR
- Abandoned (author unresponsive, no recent commits)
- Out of scope or irrelevant

Do NOT auto-close PRs that:
- Have recent activity (last 30 days)
- Are marked as draft and actively being worked on

PHASE 3: Present findings for approval

For each PR recommended for closure, output:
1. **PR link**: Full GitHub URL
2. **Title**: The PR title
3. **Author**: Who opened it
4. **Age**: Days since created / last updated
5. **Reason**: Clear explanation of why this should be closed (2-3 sentences with evidence)

Example format:
```
PR: https://github.com/org/repo/pull/123
Title: "fix stuff"
Author: @username (last active 90 days ago)
Reason: Stale — no activity for 90 days, vague title with no description, 
        only touches test files with no clear purpose. Recommend closing.
```

After presenting all findings, ask: "Close these PRs? (y/n or specify which ones)"

Only after user confirms, close with:
```sh
gh pr close "$PR" --comment "Closing: <reason>"
```
