---
name: execplan-create
description: >-
  Create an ExecPlan from a locked refactor decision, PRD, RFC, or detailed problem statement, following the repo's PLANS.md. Use when the user asks for an exec plan, execution plan, or ExecPlan, or wants a decided refactor turned into a step-by-step plan.
---

# ExecPlan Authoring

Write plans the way a strong software designer would: not as a task list for rearranging code, but as a path to a simpler system with clearer boundaries.

## Preferred Inputs

Preferred source input is a decided work item produced by `select-refactor`.

Supported inputs, in priority order:

1. explicit work-item path
2. explicit `decision.md` path
3. `.agent/active` when it points at a work item with `stage="decision"` and `state="completed"`
4. the most recently updated work item under `.agent/work/` with `stage="decision"` and `state="completed"`
5. a user-supplied PRD, RFC, voice note, or detailed problem statement

If using a decided work item, do not silently reopen candidate search unless the decision artifact is clearly incomplete.

## Work Item Model

For the new workflow, plans live inside work-item directories:

`.agent/work/<id-slug>/execplan.md`

Each work item should have a small `meta.json` file with:

- `stage`
- `state`
- timestamps
- relative artifact paths

Update `.agent/active` as a convenience symlink when operating on a work item, but do not treat it as authoritative over `meta.json`.

Legacy compatibility:

- If no work-item directory is available and the user explicitly wants the older singleton flow, you may still write `.agent/execplan-pending.md`.
- Downstream skills will prefer the work-item format and only fall back to legacy singleton files when needed.

## Source of Truth

- Read `{baseDir}/.agent/PLANS.md` in full before drafting.
- If `{baseDir}/.agent/PLANS.md` is missing, copy this skill's `PLANS.md` to `{baseDir}/.agent/PLANS.md`, then read that copy as the source of truth.
- Follow PLANS.md exactly. If any instruction conflicts with this skill, PLANS.md wins.

## Ousterhout Lens

Use John Ousterhout's design philosophy as the default planning lens:

- prefer deep modules over shallow wrappers
- prefer interfaces that hide sequencing and policy
- prefer fewer concepts and fewer special cases
- prefer simpler mental models over elegant-looking decomposition
- prefer concentrating complexity behind a stable boundary over spreading it around

Treat these as the main forms of complexity:

- change amplification
- cognitive load
- unknown unknowns

When authoring a plan, answer these questions explicitly:

- what complexity exists today, and who pays for it
- what boundary or interface becomes simpler after this work
- what knowledge moves out of callers and into the implementation
- what special cases, duplicate concepts, or orchestration steps disappear
- what future change becomes easier after this work

## Workflow

### Step 1: Resolve the input source

If operating on a decided work item:

- read `meta.json`
- read `decision.md`

If operating from a raw user brief instead:

- create or reuse a work-item directory under `.agent/work/`
- initialize or update `meta.json`
- use the user brief as the planning source

### Step 2: Inspect the repo and planning boundaries

Inspect the relevant files and flows. Ask:

- what callers currently need to know
- where sequencing leaks
- where concepts duplicate
- where special cases accumulate

### Step 3: Draft `execplan.md`

Write the ExecPlan to:

- work-item format: `.agent/work/<id-slug>/execplan.md`
- legacy fallback only when necessary: `.agent/execplan-pending.md`

The plan should:

- preserve the hard constraints from `decision.md`
- name the exact files and boundaries involved
- explain the current pain
- describe the intended complexity dividend
- remain self-contained and novice-friendly

### Step 4: Finalize metadata

If using a work item, update `meta.json`:

- `stage="plan"`
- `state="completed"`
- `artifacts.execplan="execplan.md"`
- `updated_at=<now>`

## Anti-Patterns

- reopening candidate search during planning without strong evidence
- writing a mechanically correct plan that preserves the same complexity under new names
- proposing thin wrappers or pass-through modules unless they clearly hide detail
- leaving key design choices to the implementer when the repo evidence is already strong
