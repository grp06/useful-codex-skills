---
name: execplan-improve
description: >-
  Reads an existing ExecPlan, deeply analyzes every referenced file and code path in the codebase, then rewrites the plan with concrete, code-grounded improvements.
  Use when user asks to improve an execplan, review a plan, make a plan better, audit an execplan, refine a plan, strengthen a plan, or says "improve the plan."
---

# Improve ExecPlan

> **Core philosophy:** Every improvement must trace back to something found in the actual code. No speculative additions. No surface-level rewording.

## Resolving the Base Repo

You may be running from a Codex worktree (e.g. `~/.codex/worktrees/<id>/<repo>/`). Worktrees are shallow copies — the main repo often has files the worktree does not. Always resolve the base repo path:

1. Check if the current working directory contains `/.codex/worktrees/` in its path.
2. If yes, extract the repo name (the last path component, e.g. `tail-bot`) and set the base repo to `~/<repo-name>`.
3. If no, the base repo is the current working directory.

When looking for `.agent/` contents (ExecPlans, potential-bugs, PLANS.md), check **both** the worktree `.agent/` and the base repo `.agent/`. Prefer the worktree copy if both exist; fall back to the base repo copy.

## Inputs

Default ExecPlan location: `.agent/execplan-pending.md`. Secondary is `.agent/potential-bugs/<plan-name>.md`. Search both the worktree and base repo `.agent/` directories.

Use a different path if the user provides one. If no ExecPlan exists in either location, tell the user and stop.

## Understand the purpose of execplans by reading PLANS.md

Read `.agent/PLANS.md` from the base repo (or worktree if present) before modifying the ExecPlan.

## Workflow

### Step 1: Parse the ExecPlan

Read the entire ExecPlan. Extract every file path, function/class/module name, command, milestone, acceptance criterion, and assumption.

### Step 2: Deep-Read Referenced Files

Read each file the plan mentions. Locate each named function/class/module. Flag anything that doesn't match reality:

- Missing or renamed files
- Different function signatures, types, or return values
- Import chains the plan doesn't account for
- Test files and test patterns actually in use
- Build/run commands the project actually uses

### Step 3: Explore Adjacent Code

Read files that import from or are imported by the referenced files. Look for:

- Existing patterns the plan should follow but doesn't mention
- Utilities the plan reinvents instead of reusing
- Conventions (naming, file structure, test layout) the plan would violate
- Related tests that would break or need updating
- Edge cases the plan misses

### Step 4: Score the Plan

Evaluate against six criteria:

| Criteria | Question |
|----------|----------|
| **Accuracy** | Do paths exist? Do signatures match? Are behaviors described correctly? |
| **Completeness** | Every file, test, import, and dependency covered? Any missing milestones? |
| **Self-containment** | Could a novice implement end-to-end with only this file? Terms defined? Commands complete? |
| **Feasibility** | Steps achievable in order? Hidden dependencies between milestones? |
| **Testability** | Concrete verification per milestone? Test paths, names, assertions specified? |
| **Safety** | Idempotent? Retriable? Destructive ops have rollback? |

### Step 5: Rewrite the Plan

Rewrite in-place at the same file path. Preserve existing `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` content.

Apply only code-grounded improvements:

- Fix inaccuracies (wrong paths, signatures, line numbers)
- Add missing files, functions, dependencies, and milestones
- Split milestones that are too large
- Fill in vague commands with working directories and expected output
- Make acceptance criteria observable and verifiable
- Define undefined jargon
- Add idempotence/recovery instructions where missing
- Specify test-first verification where feasible
- Reference actual patterns and utilities discovered in Step 3
- Ensure every PLANS.md-required section exists and is substantive

Do not change the plan's intent. Do not add milestones that don't serve the original purpose. Make the same plan more accurate, complete, and executable.

### Step 6: Summarize Changes

Append a revision note at the bottom of the plan describing what changed and why.

Report to the user:

- **Fixed**: inaccuracies corrected (wrong paths, signatures, etc.)
- **Added**: missing coverage (files, tests, milestones, commands)
- **Strengthened**: vague sections made concrete (acceptance criteria, verification steps)
- **Flagged**: risks or concerns worth attention

## Anti-Patterns

- **Surface-level rewording** — Changing prose without reading code is worthless.
- **Adding boilerplate** — Every addition must be specific to this codebase and this change.
- **Removing intent** — Improve execution detail; do not second-guess the goal.
- **Speculative additions** — Every addition must trace back to something discovered in the code.
- **Ignoring existing progress** — Preserve completed milestones. Do not uncheck work that was done.
