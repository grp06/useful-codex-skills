---
name: implement-execplan
description: >-
  Execute a pending execution plan from the .agent folder.
  Use when user asks to implement an execplan, execute the plan,
  run the pending plan, or mentions execplan-pending.md.
---

# Implement ExecPlan

Execute the pending execution plan located at `.agent/execplan-pending.md` in the current repository OR if the user mentioned another execplan at a different file path, implement that one.

Do not treat the ExecPlan as a blind checklist. Use it as the implementation contract for delivering the intended behavior and the intended simplification of the system.

## Ousterhout lens

Use John Ousterhout's design philosophy when the plan leaves room for judgment:

- prefer deep modules over shallow wrappers
- prefer interfaces that hide sequencing and policy
- prefer fewer concepts, fewer knobs, and fewer special cases
- prefer simple mental models over clever decomposition
- prefer concentrating complexity behind a stable boundary over spreading it across call sites

Treat these as the main forms of complexity:

- change amplification
- cognitive load
- unknown unknowns

When choosing between valid implementations, prefer the one that makes future readers and callers understand less.

## Workflow

1. Read the execplan in full, then read the repo's `.agent/PLANS.md` in full before coding.
2. Reconstruct the plan's intended behavior, target boundary, and complexity dividend before making changes. Identify what the rest of the system should no longer need to know after the work lands.
3. Inspect the relevant code paths before editing so you understand the actual current structure, not just the plan's summary.
4. Implement milestone by milestone. Keep the ExecPlan's `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` sections up to date as you go.
5. After each meaningful slice, run the plan's validation steps or the nearest targeted verification that proves the slice works.
6. Continue until the entire plan is complete and the promised behavior is demonstrated.
7. Once the execplan is implemented completely, rename it with a meaningful name and move it to `.agent/done`. If the `done` folder does not exist, create it.

## Implementation-First Rule

This skill is for execution, not more planning. The default expectation for an `implement-execplan` turn is that you will change code, tests, docs, or other implementation artifacts, not just rewrite the ExecPlan.

You may update the ExecPlan during implementation, but only to support implementation already underway:

- record progress you actually made
- record discoveries from code you already inspected while implementing
- tighten a milestone or acceptance criterion so it matches the code reality you are now acting on
- document a design decision that unblocks the next implementation step

Do not turn an implementation turn into another plan-improvement pass.

- Do not spend the turn hunting for more plan polish if you have not started changing the implementation.
- Do not end the turn with only ExecPlan edits unless the repository state proves the plan was already fully implemented before the turn began.
- If you discover a meaningful design adjustment, update the ExecPlan briefly, record the decision, and then continue implementing in the same turn.
- If you discover the plan is fundamentally wrong, do the smallest necessary rewrite to restore a correct implementation target, then resume coding immediately. Do not keep iterating on the plan for the rest of the turn.

A successful implementation turn should leave evidence of execution:

- changed implementation files, tests, docs, or verification artifacts
- updated ExecPlan progress that reflects completed work rather than intended work
- validation output for the slices you actually landed

## Decision Making

If a step is ambiguous or has multiple valid approaches, proceed with your best judgment rather than stopping to ask, but use these rules:

- Prefer the implementation that hides more detail behind an existing or newly deepened boundary.
- Prefer removing a special case over adding a branch that preserves it.
- Prefer one well-owned concept over parallel concepts that force readers to translate between them.
- Prefer reusing an existing strong module over adding a thin orchestration layer beside it.
- Prefer explicit design changes recorded in the ExecPlan over silent drift away from the plan.

If the best implementation requires a meaningful design adjustment, update the ExecPlan briefly, record the decision, and continue implementing in the same turn.

## Anti-Patterns

- Do not satisfy the letter of the plan while preserving the same interface burden.
- Do not add wrappers, adapters, or helper layers unless they clearly hide complexity from callers.
- Do not push sequencing or policy decisions outward to call sites when they can be owned in one place.
- Do not use this skill as another `execplan-improve` pass.
- Do not finish the turn with only ExecPlan edits when implementation work remains.
- Do not leave the ExecPlan stale while the implementation evolves.
