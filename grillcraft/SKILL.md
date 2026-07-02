---
name: grillcraft
description: >-
  Compile a completed Grill Me session, transcript, or decision discussion into
  a durable work item under `.agent/work/`: write `decision.md`, initialize
  `meta.json`, create an ExecPlan, run configurable `execplan-improve` passes,
  and invoke Goalcraft to activate a Codex `/goal` that executes the ExecPlan
  lifecycle. Use after grilling, when the user says "GrillCraft", "turn this
  grill into a goal", "create the ExecPlan and goal", "run Goalcraft after this
  grill", or asks for N ExecPlan improvements.
---

# GrillCraft

## Core Contract

Turn resolved intent into a durable execution handoff. GrillCraft is a compiler
from a Grill Me-style decision conversation into:

- `.agent/work/<slug>/decision.md`
- `.agent/work/<slug>/meta.json`
- `.agent/work/<slug>/execplan.md`
- an activated Goalcraft `/goal` that executes the work item until evidence says
  the ExecPlan and decisions are satisfied or honestly blocked.

GrillCraft owns setup and activation, not product implementation. After the
Goalcraft goal is active, the goal is the persistent executor. The goal must
absorb the implementation protocol that `implement-execplan` previously owned:
set implementation state, execute milestones, keep the ExecPlan living sections
current, validate after slices, revise the plan when evidence changes the path,
and finish only after review evidence satisfies both `decision.md` and
`execplan.md`.

## Input Resolution

Resolve the source of intent in this order:

1. explicit Grill Me transcript, decision ledger, or work-item path from the user
2. the current conversation when it clearly contains a completed grill session
3. explicit `decision.md` or `decisions.md` supplied by the user
4. `.agent/active` when it points to a work item with a decision artifact

If the source is missing, obviously incomplete, or mostly a vague brief rather
than resolved intent, stop and ask for the smallest missing artifact. Do not
invent decisions to keep the pipeline moving.

## Improvement Count

Default to 3 `execplan-improve` attempts.

If the user says `N improvements`, `N improve passes`, or equivalent, use that
integer. `0 improvements` means create the ExecPlan and skip improvement.

Treat the count as "up to N useful attempts." If `execplan-improve` returns
exactly `skip`, or its own low-value short-circuit applies, stop improvement
early and continue to Goalcraft with the current plan.

## Workflow

### Step 1: Create or reuse the work item

Prefer the work-item format:

```text
.agent/work/<slug>/
  meta.json
  decision.md
  execplan.md
```

If updating an existing work item, read `meta.json`, `decision.md`, and
`execplan.md` if present before writing. Preserve unrelated artifacts and do not
rename directories to represent lifecycle state.

Use `.agent/active` only as a convenience symlink. The authoritative lifecycle
state lives in `meta.json`.

### Step 2: Write `decision.md`

Distill the grill into a provenance-aware decision artifact. Use `decision.md`
singular, even if the user says `decisions.md`, because downstream ExecPlan
skills already prefer that path.

`decision.md` should contain:

- Objective
- Confirmed user decisions
- Agent-recommended defaults
- Assumptions
- Open questions or user judgments
- Accepted risks and failure modes
- Validation expectations
- Source notes naming the transcript, files, or conversation basis

Do not dump the whole transcript. Keep decisions compact enough that a future
agent can recover intent quickly, while preserving whether each item is
confirmed, inferred, assumed, or still open.

### Step 3: Initialize metadata

Write or update `meta.json` with:

- `stage="decision"`
- `state="completed"`
- timestamps
- `artifacts.decision="decision.md"`

If the work item came from a parent meta-plan, preserve `meta_plan_id` and
`meta_plan_slice_id`.

### Step 4: Create the ExecPlan

Use the existing `$execplan-create` protocol on the work item. The resulting
plan must live at `.agent/work/<slug>/execplan.md` and follow `.agent/PLANS.md`.

The ExecPlan must be self-contained per `PLANS.md`, but it may cite
`decision.md` as the provenance record. Preserve hard constraints from
confirmed decisions, clearly label assumptions and open judgments, and make the
validation surface observable.

### Step 5: Improve the ExecPlan

Run `$execplan-improve` up to the requested number of attempts, defaulting to 3.
Each pass must be code-grounded. Do not ask for cosmetic rewrites.

After improvement, keep the work item at:

- `stage="plan"`
- `state="completed"`
- `artifacts.execplan="execplan.md"`

### Step 6: Invoke Goalcraft

Use `$goalcraft` with a compact brief that references the work item and tells
the goal to execute the ExecPlan lifecycle. Include this execution contract in
the Goalcraft input:

```text
Operate the work item at .agent/work/<slug>. Treat decision.md as the
intent/provenance source and execplan.md as the executable contract governed by
.agent/PLANS.md. Before coding, set meta.json to stage="implementation" and
state="active". Execute execplan.md milestone by milestone. Keep Progress,
Surprises & Discoveries, Decision Log, and Outcomes & Retrospective current.
After each meaningful slice, run the plan's validation or the nearest targeted
check. If evidence changes the path, revise execplan.md before continuing. Do
not mark complete because of elapsed time, budget exhaustion, partial
implementation, or proxy checks alone. Done only after implementation,
validation, and a fresh review-style pass satisfy both decision.md and
execplan.md. If blocked, record the blocker in execplan.md and meta.json,
including what user input or external change would unblock progress.
```

If the user requested draft-only, planning-only, no-goal mode, or no activation,
prepare the Goalcraft-ready objective but do not activate it.

If another unfinished goal already exists, do not silently replace it. Let
Goalcraft handle the conflict, and return the validated goal text as the
fallback artifact if activation cannot proceed.

## Anti-Patterns

- implementing product code during GrillCraft setup
- flattening agent recommendations into confirmed user decisions
- dumping transcript history into `decision.md`
- creating a meta-plan unless the user explicitly asks for parent/child slices
- forcing all requested improvement passes after `execplan-improve` says `skip`
- treating the Goal as the plan instead of a compact execution loop around the
  work item
- marking the work item implementation-active before Goalcraft actually begins
  execution
