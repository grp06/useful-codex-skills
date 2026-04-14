---
name: execplan-improve
description: >-
  Read an existing ExecPlan, deeply analyze every referenced file and code path, and rewrite the plan with concrete, code-grounded improvements. Prefer work-item plans under `.agent/work/`, while preserving backward-compatible support for older singleton plan files.
---

# Improve ExecPlan

> **Core philosophy:** Every improvement must trace back to something found in the actual code. No speculative additions. No surface-level rewording.

## Ousterhout Lens

Use John Ousterhout's design philosophy as the design-quality lens:

- prefer deep modules over shallow wrappers
- prefer interfaces that hide sequencing and policy details
- prefer fewer concepts, fewer knobs, and fewer special cases
- prefer simpler mental models over visually tidy decomposition
- prefer moving complexity behind a stable boundary over redistributing it

Treat these as the main forms of complexity:

- change amplification
- cognitive load
- unknown unknowns

## Resolving the Base Repo

You may be running from a Codex worktree such as `~/.codex/worktrees/<id>/<repo>/`.

1. If the current path contains `/.codex/worktrees/`, set the base repo to `~/<repo-name>`.
2. Otherwise the base repo is the current working directory.

Check both the worktree `.agent/` and the base repo `.agent/`. Prefer the worktree copy if both exist.

## Input Resolution

Preferred target resolution order:

1. explicit plan path supplied by the user
2. explicit work-item path supplied by the user
3. `.agent/active` when it points to a work item with `stage="plan"` and `state="completed"`
4. the most recently updated work item under `.agent/work/` with `stage="plan"` and `state="completed"`
5. legacy fallback: `.agent/execplan-pending.md`
6. explicit legacy fallback: `.agent/potential-bugs/<plan-name>.md`

If no ExecPlan exists in any supported location, tell the user and stop.

## Understand the Purpose of ExecPlans

Read `.agent/PLANS.md` from the base repo or worktree before modifying the plan.

## Workflow

### Step 0: Short-Circuit Low-Value Repeats

Before doing repo work, inspect only the immediately previous assistant turn.

- If the previous `execplan-improve` result was exactly `skip`, return exactly `skip`.
- If it ended with `Usefulness score: N/10 - ...` and `N <= 3`, return exactly `skip`.

### Step 1: Resolve the plan path and work-item metadata

If operating on a work item, read:

- `meta.json`
- `decision.md` when present
- `execplan.md`

Otherwise read the legacy plan path directly.

### Step 2: Parse the ExecPlan

Extract:

- file paths
- symbols
- commands
- milestones
- acceptance criteria
- assumptions

### Step 3: Deep-read referenced and adjacent code

Read the referenced files and nearby importers/importees. Look for:

- wrong paths or signatures
- missing tests or dependencies
- project conventions the plan misses
- leaked sequencing or policy the plan should hide
- shallow abstractions the plan preserves without reason
- duplicate concepts or special-case branches the plan could absorb

### Step 4: Audit the plan

Check:

- accuracy
- completeness
- self-containment
- feasibility
- testability
- safety
- design quality

### Step 5: Rewrite the plan in place

Rewrite at the same path:

- work-item format: `execplan.md`
- legacy format: the original singleton path

Preserve existing `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective`.

Apply only code-grounded improvements:

- fix inaccuracies
- add missing files, tests, dependencies, milestones, and commands
- split oversized milestones
- define jargon
- make acceptance criteria observable
- add recovery guidance where missing
- strengthen the intended simplicity boundary and complexity dividend

Do not change the plan's intent.

### Step 6: Finalize metadata

If using a work item, keep:

- `stage="plan"`
- `state="completed"`
- `updated_at=<now>`

### Step 7: Score usefulness and summarize

Report:

- **Fixed**
- **Added**
- **Strengthened**
- **Flagged**
- final line: `Usefulness score: X/10 - <specific reason>`

If a real pass found no material improvements, return exactly `skip`.

## Anti-Patterns

- surface-level rewording without code evidence
- speculative additions
- changing the plan's goal
- ignoring existing progress
- preserving shallow or leaky abstractions just because they were already in the draft
