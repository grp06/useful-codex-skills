---
name: review-recent-work
description: >-
  Review the latest implemented work item or completed ExecPlan with fresh eyes, fix obvious issues immediately, rerun verification, and record the result. Prefer the new `.agent/work/` workflow, but preserve backward-compatible support for older `.agent/done/` ExecPlans.
---

# Review Recent Work

Review the latest implemented work item as a fresh-eyes code review pass. Fix issues now when the right improvement is clear and bounded. End with a usefulness score for the review-and-fix pass itself.

This skill is intended to run immediately after `$implement-execplan`.

## Ousterhout Lens

The review should answer two questions:

- is the new behavior correct
- did the implementation actually achieve the intended simplicity boundary

## Resolving the Base Repo

You may be running from a Codex worktree such as `~/.codex/worktrees/<id>/<repo>/`.

1. If the current path contains `/.codex/worktrees/`, set the base repo to `~/<repo-name>`.
2. Otherwise the base repo is the current working directory.

Check both worktree and base repo `.agent/` contents. Prefer the worktree copy if both exist.

## Preferred Input Resolution

Preferred target resolution order:

1. explicit work-item path supplied by the user
2. explicit `execplan.md` path supplied by the user
3. `.agent/active` when it points to a work item with either:
   - `stage="implementation"` and `state="completed"`, or
   - legacy-compatible `stage="review"` and `state="completed"`
4. the most recently updated work item under `.agent/work/` matching the same rules
   - prefer the active completed implementation when one exists
   - do not exclude already-reviewed items, because repeat review passes are allowed
5. legacy fallback: prefer the most recently modified Markdown file under `.agent/done/`; if none exists, fall back to `.agent/execplan-pending.md`

If no supported completed implementation exists, stop and tell the user.

## Work Item Responsibilities

If operating on a work item, read:

- `meta.json`
- `decision.md` when present
- `execplan.md`

If the child work item contains:

- `meta_plan_id`
- `meta_plan_slice_id`

then this skill also owns reconciling the reviewed child result back into the
matching parent meta-plan under `.agent/meta-plans/`.

This skill owns:

- keeping review metadata additive rather than advancing the work item out of completed implementation

Review is not a separate lifecycle stage. The lifecycle fact that matters is that implementation completed.

Work-item compatibility rules:

- If a work item is already at `stage="review"` and `state="completed"` from an older pass, treat it as a valid completed implementation target.
- After a successful review pass, normalize the work item back to `stage="implementation"` and `state="completed"`.
- Do not write a repo-local review artifact such as `review.md`; return the review findings in the assistant response only.

## Workflow

### Step 0: Short-Circuit Low-Value Repeats

Before doing repo work, inspect only the immediately previous assistant turn.

- If the user explicitly asks for another review pass, a second review, or a fresh-eyes rerun, do not short-circuit.
- Otherwise, if the immediately previous `review-recent-work` result was exactly `skip`, return exactly `skip`.
- Otherwise, if it ended with `Usefulness score: N/10 - ...` and `N <= 3`, return exactly `skip`.

### Step 1: Resolve the review target

If operating on a work item, treat the target as the combination of:

- `decision.md`
- `execplan.md`
- the observable recent implementation surface

If using the legacy fallback, treat the selected legacy plan path as the implementation contract.

### Step 2: Build the review surface

Inspect:

- `git status --short`
- `git diff --stat`
- `git diff`
- `git log -1 --stat --name-only`

Treat the review surface as the union of:

- files explicitly named in the plan
- files implicated by `decision.md` when present
- files currently changed in git
- files touched by the most recent commit when the tree is clean
- adjacent tests, helpers, and importers needed to judge correctness

If the selected work item and the observable recent code changes clearly do not overlap, stop and report that mismatch.

### Step 3: Reconstruct intent

Use `decision.md` when present to understand:

- why this refactor was chosen
- what success meant
- what the first slice was supposed to achieve
- what risks were considered acceptable

Use `execplan.md` to understand:

- planned behavior
- touched files
- validation commands
- acceptance criteria

### Step 4: Perform a real code review

Prioritize:

- correctness bugs
- behavioral regressions
- missing error handling
- validation gaps
- missing or weak tests
- partial refactors and dead code
- shallow wrappers or pass-through abstractions
- leaked sequencing or policy
- scope expansion away from the original decision rationale

### Step 5: Fix obvious issues now

If the right improvement is clear and bounded, make the fix immediately.

Keep the scope tight. Do not turn the review into a broad redesign.

### Step 6: Re-run verification

Run the verification commands from the plan whenever they still apply. Add targeted tests or lint commands needed to validate the review fixes.

If verification cannot be run, say exactly why.

### Step 7: Finalize metadata

If operating on a work item, update `meta.json`:

- `stage="implementation"`
- `state="completed"`
- `updated_at=<now>`

### Step 8: Reconcile back into the parent meta-plan when present

If the reviewed child work item has `meta_plan_id` and `meta_plan_slice_id`:

- load the parent meta-plan directory under `.agent/meta-plans/<meta_plan_id>/`
- read parent `meta.json`
- read parent `slices.json`
- update the matching slice:
  - set `status="completed"` when the child remains `stage="implementation"` and `state="completed"`
  - set `status="blocked"` only when the child work item ended blocked
  - do not leave a finished slice as `active` or `ready`
- write a short `result_summary`
- append one concise note to the slice `notes`
- advance `active_slice_id` to the next slice whose `depends_on` entries are all completed
- if a next slice is chosen, mark it `active`
- if no slices remain incomplete, mark the parent meta-plan `status="completed"`
- otherwise keep the parent meta-plan `status="active"` or `status="blocked"` to match the frontier

Reconcile against the final reviewed child state, not the pre-review state.

Do not create a separate `update-meta-plan` artifact or workflow in this skill.

### Step 9: Summarize the pass

Report:

- findings ordered by severity when any exist
- what you changed
- what you validated
- whether the implementation achieved the intended complexity dividend
- remaining risks
- final line: `Usefulness score: X/10 - <specific reason>`

## Anti-Patterns

- reviewing unrelated old changes just because they are nearby
- inventing problems to justify a higher score
- leaving obvious, safe findings unfixed
- replacing verification with speculation
- judging the implementation only against the plan and ignoring the original decision rationale
- updating the parent meta-plan before the child review result is final
