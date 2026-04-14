---
name: select-refactor
description: Read a refactor candidate shortlist, pressure-test the leading options with cheap repo evidence, and lock the final refactor choice in a work item before planning. Use when the user wants the best refactor chosen from a shortlist, wants the current favorite challenged, or wants a final decision before creating an ExecPlan.
---

# Select Refactor

## Goal

Turn a refactor shortlist into a locked decision.

This skill is the commitment step between search and planning. It should pressure-test the current leader, gather cheap disconfirming evidence, compare runner-ups honestly, and then freeze one decision so `execplan-create` does not have to silently re-open the search space.

Do not create an ExecPlan here.

## Work Item Resolution

Preferred target resolution order:

1. explicit work-item path supplied by the user
2. explicit `candidates.md` or `decision.md` path supplied by the user
3. `.agent/active` when it points to a work item with `stage="candidates"` and `state="completed"`
4. the most recently updated work item under `.agent/work/` with `stage="candidates"` and `state="completed"`

If no candidate work item exists, stop and tell the user to run `find-refactor-candidates` first.

This skill owns:

- `decision.md`
- updates to `meta.json`

## Ousterhout Lens

Use John Ousterhout's design philosophy as the design lens:

- prefer deep modules over shallow wrappers
- prefer interfaces that hide sequencing and policy details
- prefer fewer concepts and fewer special cases
- prefer simpler mental models over structurally tidy but leaky decompositions

Treat these as the main forms of complexity:

- change amplification
- cognitive load
- unknown unknowns

## Selection Rule

The job is not to "polish the current favorite." The job is to decide which candidate survives criticism best.

Every pre-planning cycle inside this skill must end by doing at least one of these:

- introducing one materially new candidate
- deleting a candidate from serious consideration
- changing confidence based on new repo evidence

If a cycle does none of those things, it is probably only producing nicer prose.

## Workflow

### Step 1: Read the candidate brief and current metadata

Read:

- `meta.json`
- `candidates.md`

Extract:

- candidate set
- provisional leader
- assumptions and falsifiers
- cheapest probes
- repo constraints

### Step 2: Adversarial challenge pass

Assume the provisional leader may be wrong.

Attack it directly:

- what hidden coupling makes it costlier than it looks
- what repo evidence contradicts it
- what simpler alternative gets most of the benefit
- what runner-up becomes stronger if the leader's main assumption fails
- whether the minimal surgical change or do-nothing option actually dominates under the stated risk tolerance

### Step 3: Cheap evidence round

Spend a bounded amount of repo work on cheap evidence before commitment. Favor disconfirming evidence over elaboration.

Useful probes include:

- call-site and import fan-out
- dependency graph or import graph inspection
- churn or co-change history
- nearby tests and fragility
- ownership boundaries
- API surface spread
- tiny probes or repros that do not edit code

Do not drift into planning or implementation.

### Step 4: Lock the decision

Choose the winning refactor and write `decision.md` with:

1. chosen refactor
2. why it beats the alternatives now
3. what evidence changed confidence
4. why the runner-ups lost
5. success criteria
6. first safe slice
7. abandonment conditions
8. what `execplan-create` should preserve as hard constraints

`decision.md` is the planning input artifact.

### Step 5: Finalize metadata

Update `meta.json`:

- `stage="decision"`
- `state="completed"`
- `artifacts.decision="decision.md"`
- `updated_at=<now>`

## Anti-Patterns

- merely rephrasing the provisional leader
- treating critique as decorative instead of decision-changing
- reopening the entire search space without new evidence
- creating `execplan.md` here
- leaving the decision implicit
