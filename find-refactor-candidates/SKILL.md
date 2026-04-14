---
name: find-refactor-candidates
description: Search a repo for the top 3-5 materially different refactor opportunities, record the evidence for each, and create a work item for later selection and planning. Use when the user wants the best refactor, highest-leverage cleanup, architectural simplification, boundary extraction, duplication removal, or a shortlist of strong refactor options before choosing one.
---

# Find Refactor Candidates

## Goal

Search the repo from first principles and produce a **materially different** shortlist of refactor hypotheses before commitment hardens.

This skill is a search step, not a planning step and not a final-decision step.

Do not ask the user to choose among options. Do not create an ExecPlan. Leave behind a work item that `select-refactor` can pressure-test and decide.

## Work Item Model

Use one stable work-item directory per initiative:

`.agent/work/<YYYY-MM-DD-HHMM>-<slug>/`

Inside that directory, this skill owns:

- `meta.json`
- `candidates.md`

The work-item directory is the source of truth for this initiative. Do not encode lifecycle state in filenames or by moving files between folders.

Create or update `.agent/active` as a convenience symlink pointing at the current work item, but do not rely on the symlink as the authoritative state source.

### `meta.json` shape

Keep the metadata intentionally small:

```json
{
  "id": "2026-04-14-1030-auth-boundary-owner",
  "slug": "auth-boundary-owner",
  "title": "Auth boundary owner refactor",
  "created_at": "2026-04-14T17:30:00Z",
  "updated_at": "2026-04-14T18:10:00Z",
  "stage": "candidates",
  "state": "completed",
  "artifacts": {
    "candidates": "candidates.md",
    "decision": null,
    "execplan": null,
    "review": null
  }
}
```

Use these values:

- `stage`: `candidates`
- `state`: `active`, `blocked`, `completed`, or `abandoned`

For this skill, the normal final state is `stage="candidates"` and `state="completed"`.

## Ousterhout Lens

Use John Ousterhout's design philosophy as the primary lens:

- prefer simple mental models over elegant-looking structure
- prefer deep modules over shallow wrappers
- prefer interfaces that hide sequencing and policy details
- prefer fewer concepts and fewer special cases
- prefer moving complexity behind a stable boundary over redistributing it

Treat these as the main forms of complexity:

- change amplification
- cognitive load
- unknown unknowns

The question is:
"What are the strongest plausible refactor directions, before we decide which one deserves commitment?"

## User Guidance Handling

Treat user guidance as either:

- **Hard constraints**: explicit scope, risk, or prohibitions
- **Soft guidance**: hints, priors, or suspected messy areas

Rules:

- Honor hard constraints strictly.
- Treat soft guidance as weighting, not proof.
- If the user says "planning only" or "do not implement," treat that as a hard no-edit constraint on the codebase. Creating or updating work-item artifacts under `.agent/` is still allowed because this skill is itself a planning workflow.

## Workflow

### Step 1: Resolve scope and work item

Determine:

- target repo or directory
- hard constraints
- soft guidance
- risk tolerance

If the user explicitly references an existing work-item directory, reuse it.

Otherwise:

1. Create `.agent/work/` if missing.
2. Derive a descriptive slug from the current best theme, not from a final locked decision.
3. Create a new work-item directory with timestamp plus slug.
4. Initialize `meta.json`.
5. Update `.agent/active` to point at this directory.

### Step 2: Build a first-principles repo model

Read the codebase systematically:

1. Start with `README`, `ARCHITECTURE.md`, or similar docs.
2. Identify languages, frameworks, major entry points, and the most central modules.
3. Map 3-5 core flows.
4. Collect lightweight evidence:
   - import/reference frequency
   - file size and directory spread
   - change frequency when git history is available
   - co-change evidence
   - nearby tests
   - whether the area is core or niche

### Step 3: Generate materially different candidates

Generate 3-5 candidates that are genuinely different from one another.

Required candidate set rules:

- Include one `do nothing` option.
- Include one `minimal surgical change` option.
- Do not produce 3-5 variants of the same abstraction move.

Good candidate classes include:

- deepen a shallow module
- hide sequencing or policy
- consolidate duplicate concepts
- eliminate special-case complexity
- remove a stale layer

### Step 4: Write an assumption ledger for each candidate

For each candidate, capture:

- candidate name
- refactor class
- scope: files and flows involved
- the problem it believes it is solving
- supporting repo evidence
- contradictory or weakening repo evidence
- what would falsify it
- expected payoff
- blast radius
- reversibility
- the cheapest useful probe

### Step 5: Rank candidates without locking the decision

Score candidates with a lightweight rubric:

- complexity removed from callers and readers
- information-hiding gain
- cognitive load reduction
- change amplification reduction
- special-case elimination
- blast radius vs risk
- evidence confidence

Name a **provisional leader**, not a final winner.

### Step 6: Write `candidates.md`

Write `candidates.md` with:

1. repo scope and constraints
2. first-principles repo model
3. ranked shortlist
4. full assumption ledger per candidate
5. provisional leader
6. why each runner-up is still alive
7. the next step for `select-refactor`

The next step must be selection, not planning.

### Step 7: Finalize metadata

Update `meta.json`:

- `stage="candidates"`
- `state="completed"`
- `artifacts.candidates="candidates.md"`
- `updated_at=<now>`

## Anti-Patterns

- offering a single winner with no serious alternatives
- omitting the `do nothing` option
- omitting the `minimal surgical change` option
- creating candidates that are cosmetic variants of one idea
- creating `decision.md` or `execplan.md` in this skill
- asking the user to choose among the candidates
