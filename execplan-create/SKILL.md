---
name: execplan-create
description: >-
  Create an ExecPlan (execution plan) from a PRD, RFC, voice note, or
  brainstorming blurb, following the repo's PLANS.md. Use when the user asks
  for an exec plan, execution plan, or ExecPlan, or wants a PRD/RFC turned into
  a step-by-step plan.
---

# ExecPlan Authoring

Write plans the way a strong software designer would: not as a task list for rearranging code, but as a path to a simpler system with clearer boundaries.

## Required inputs

- The user must provide a PRD, RFC, or a detailed problem statement. If missing or unclear, ask for clarification before writing the plan.

## Source of truth

- Read `{baseDir}/.agent/PLANS.md` in full before drafting.
- If `{baseDir}/.agent/PLANS.md` is missing, copy this skill's `PLANS.md` to `{baseDir}/.agent/PLANS.md`, then read that copy as the source of truth.
- Follow PLANS.md exactly. If any instruction conflicts with this skill, PLANS.md wins.

## Ousterhout lens

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

When authoring a plan, answer these questions explicitly in the plan's prose:

- what complexity exists today, and who pays for it
- what boundary or interface becomes simpler after this work
- what knowledge moves out of callers and into the implementation
- what special cases, duplicate concepts, or orchestration steps disappear
- what future change becomes easier after this work

Reject plan shapes that mainly add new layers, knobs, or abstraction names without hiding more detail.

## Output location

- Write the ExecPlan to `.agent/execplan-pending.md` in the target repo.
- If `.agent/` does not exist, create it before writing the file.

## Format rules

- Because `.agent/execplan-pending.md` contains only the ExecPlan, do not wrap it in outer triple backticks.

## Authoring workflow

1. Read the user's input and identify the concrete outcomes, acceptance criteria, hard constraints, and any soft guidance about scope or risk.
2. Inspect the repo to understand the relevant files, current flows, and the complexity being paid today. Ask: what do callers currently need to know, where does sequencing leak, where are concepts duplicated, and where do special cases accumulate.
3. Decide the plan shape that most reduces system complexity while still satisfying the request. Prefer the path that creates a simpler interface or a deeper owned module, not the one that merely redistributes logic.
4. Draft the ExecPlan using the skeleton and rules from PLANS.md. Name the exact files and boundaries involved, explain the current pain, and describe the complexity dividend the change is intended to produce.
5. Ensure required sections exist and are self-contained, novice-friendly, behavior-focused, and explicit about why the design is simpler after the change.
6. Save to `.agent/execplan-pending.md`.

## Anti-patterns

- Do not write a mechanically correct plan that preserves the same complexity under new names.
- Do not propose thin wrappers or pass-through modules unless the plan can explain exactly what detail they hide.
- Do not leave key design choices to the implementer when the repo evidence is strong enough to decide now.
