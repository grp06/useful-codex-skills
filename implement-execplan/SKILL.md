---
name: implement-execplan
description: >-
  Execute an ExecPlan from a work item under `.agent/work/` or, when necessary, from the older singleton `.agent/execplan-pending.md` flow. Use when the user asks to implement a plan, execute the pending plan, or resume blocked implementation work.
---

# Implement ExecPlan

Use the ExecPlan as the implementation contract for delivering both the intended behavior and the intended simplification of the system.

## Preferred Input Resolution

Preferred target resolution order:

1. explicit work-item path supplied by the user
2. explicit `execplan.md` path supplied by the user
3. `.agent/active` when it points to a work item with:
   - `stage="plan"` and `state="completed"`, or
   - `stage="implementation"` and `state="blocked"`
4. the most recently updated work item under `.agent/work/` matching those same rules
5. legacy fallback: `.agent/execplan-pending.md`

If no supported plan exists, stop and tell the user.

## Work Item Responsibilities

If operating on a work item, read:

- `meta.json`
- `decision.md` when present
- `execplan.md`

This skill owns execution-state transitions in `meta.json`:

- when starting work: `stage="implementation"`, `state="active"`
- when blocked or only partially complete: `stage="implementation"`, `state="blocked"`
- when implementation completes: `stage="implementation"`, `state="completed"`

Do not rename plans or move directories to represent lifecycle state.

## Ousterhout Lens

When the plan leaves room for judgment:

- prefer deep modules over shallow wrappers
- prefer interfaces that hide sequencing and policy
- prefer fewer concepts, fewer knobs, and fewer special cases
- prefer simple mental models over clever decomposition

## Workflow

1. Read the ExecPlan in full, then read `.agent/PLANS.md`.
2. Reconstruct the intended behavior, target boundary, and complexity dividend.
3. If available, read `decision.md` so the implementation stays aligned with the original decision rationale.
4. Before coding, update `meta.json` to `stage="implementation"` and `state="active"`.
5. Inspect the relevant code paths before editing.
6. Implement milestone by milestone.
7. Keep the ExecPlan's `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` sections up to date as you go.
8. After each meaningful slice, run the plan's validation steps or the nearest targeted verification.
9. If you finish the implementation, set `state="completed"`.
10. If you cannot finish safely in the current turn, record the blocker in the plan, set `state="blocked"`, and stop cleanly.

## Implementation-First Rule

This skill is for execution, not more planning.

You may update the ExecPlan during implementation only to:

- record progress actually made
- record discoveries from code already inspected
- tighten milestones or acceptance criteria to match current repo reality
- document design decisions that unblock the next implementation step

Do not turn an implementation turn into another plan-improvement pass.

## Anti-Patterns

- satisfying the letter of the plan while preserving the same interface burden
- adding wrappers, adapters, or helper layers that hide little
- pushing sequencing or policy outward to callers
- finishing with only ExecPlan edits when implementation work remains
- using file moves or renames as the primary state transition
