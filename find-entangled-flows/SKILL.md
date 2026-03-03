---
name: find-entangled-flows
description: >-
  Scan a codebase to find THE SINGLE MOST MEANINGFUL entanglement where core domain logic and infrastructure side effects (I/O, HTTP, DB, filesystem, queues) are architecturally entangled — not at the function level, but at the flow and module level. Picks one decisive extraction and writes an ExecPlan to .agent/execplan-pending.md.
  Use when user asks to find the worst boundary violation, find the most critical seam, identify the most impactful side-effect coupling, or find the single most problematic architectural entanglement.
---

# Find The Most Meaningful Entanglement

## Mindset: Think Like a Systems Architect Finding the Worst Offender

You are not looking for individual impure functions. You are looking for **THE SINGLE flow or module where domain logic and infrastructure are so entangled that you cannot test, replace, or reason about one without dragging in the other — AND where fixing it would have the greatest positive impact.**

This is the place where:
- Mocking hell lives — you need 6 mocks to test one business rule
- Bugs cascade — a database timeout causes a business logic error because they share a call stack
- Changing an API provider means rewriting decision logic
- Nobody writes tests because the setup cost is insane

**The question you are answering:** "Where in this codebase is the WORST case of domain rules held hostage by infrastructure?"

**Be decisive. Do not ask clarifying questions.** You have the codebase. Read it. State your assumptions and proceed.

---

## Workflow

### Step 1: Establish Scope

Determine scope from context. Default to workspace root if unspecified. Read `README`, `ARCHITECTURE.md`, or equivalent to understand the system's intended boundaries.

Identify language(s), framework(s), and project structure by reading config files and the directory tree.

### Step 2: Map Core User Flows

Identify the 3-5 most important user-facing flows in the system (e.g., "user signs up", "order is placed", "report is generated"). Trace each flow through the codebase from entry point to completion.

For each flow, track:
- Where domain decisions happen (validation, authorization, state transitions, calculations, business rules)
- Where side effects happen (DB writes, API calls, file I/O, message sends, cache operations)
- **Whether those two things can be separated without rewriting the flow**

### Step 3: Identify Structural Entanglement

Look for these systemic patterns — not individual functions, but architectural-level problems:

**God flows** — An entire user-facing operation (signup, checkout, sync) implemented as one long procedural chain where domain rules, DB calls, API fetches, and notifications are interleaved in a single call stack. You can't test the business rules without standing up the entire infrastructure.

**Domain logic buried in infrastructure adapters** — Business rules living inside API route handlers, database repositories, queue consumers, or middleware. The "what should happen" is inseparable from the "how it talks to the outside world."

**Implicit state machines** — A flow that transitions through states (pending → approved → fulfilled) but the transition logic is scattered across multiple side-effecting functions rather than being expressed as a pure state machine that infrastructure calls into.

**Data transformation pipelines coupled to I/O at every step** — Fetch → transform → fetch more based on result → transform again → write. The transformation logic is correct but untestable because it's woven between I/O calls.

**Shared mutable state between boundary and core** — Infrastructure and domain logic sharing mutable objects, where side effects modify data that business rules later read from the same reference, making the flow order-dependent and fragile.

### Step 4: Score All Candidates

For each entanglement candidate you've identified, score it using this rubric:

| Criteria | Weight |
|----------|--------|
| Blast radius — how much of the system depends on this flow staying entangled | 30% |
| Testability damage — how hard is it to test the domain logic in isolation right now | 25% |
| Bug surface — does this entanglement cause or mask real bugs, or is it just ugly | 20% |
| Change frequency — how often does this area get modified (high churn = high pain) | 15% |
| Separation feasibility — can you actually pull these apart without rewriting everything | 10% |

Calculate a weighted score for each candidate. The highest-scoring entanglement is your answer.

### Step 5: Present THE ONE Most Meaningful Entanglement

Present only the single highest-impact boundary violation using this format:

```
## The Most Meaningful Entanglement: [Name of the flow or module]

**Scope:** [files/directories involved — be specific]
**Impact:** Critical

**The entanglement:**
[Describe the flow end-to-end. Show how domain logic and infrastructure are woven together. Reference specific files and line ranges.]

**What's held hostage:**
[What domain rules or business logic can't be tested, reused, or changed independently because of this coupling?]

**The damage:**
[Concrete consequences — untestable flows, cascading failures, inability to swap providers, onboarding friction, bug classes that exist because of this structure.]

**Why this is THE worst one:**
[Briefly explain your scoring rationale — why this entanglement scored higher than other candidates you considered.]
```

### Step 6: Pick THE One Extraction and Write the ExecPlan

This is the decisive step. Do not present options. Do not ask the user to choose. **You pick.**

From the entanglement identified in Step 5, select the single highest-ROI extraction — the one concern or flow to pull out first. Pick the extraction that:
- Removes the most lines and complexity from the entangled module
- Has the clearest seam to cut along (fewest cross-references to other entangled logic)
- Produces a unit that is independently testable with pure inputs/outputs
- Requires the least churn to adjacent, uninvolved code

#### Source of truth for plan format

Read `PLANS.md` in the target repo root. If missing, read `{baseDir}/PLANS.md` (bundled with the `execplan-create` skill at `$CODEX_HOME/skills/execplan-create/PLANS.md`). Follow that format exactly.

#### Write the ExecPlan

Create `.agent/` if it does not exist. Write the plan to `.agent/execplan-pending.md`. The plan must be self-contained — a novice with only this file can execute the extraction. Map your findings to the required sections:

- **Purpose / Big Picture** — State the entanglement problem in 2-3 sentences. What the user gains: the extracted domain logic becomes independently testable and the source file becomes pure wiring. This is a pure refactor — no user-visible behavior change.
- **Context and Orientation** — Name every file involved with full repo-relative paths. Describe the source file's role, its current line count, and the specific concern being extracted. Define any domain terms. Include the line ranges you identified in Step 5 so the implementer knows exactly where to cut.
- **Plan of Work** — Describe the extraction in prose: what moves, where it goes, what the new module's interface looks like (inputs/outputs), and how the source file calls it afterward. Name the new file path.
- **Concrete Steps** — Exact commands: create file, move logic, update imports, run typecheck, run tests. Include the working directory and expected output for each command.
- **Validation and Acceptance** — Specify: the source file reduced by ~N lines, the extracted module has zero direct imports of infrastructure concerns (list them), all existing tests pass (exact command), specific user-facing flows still work, no new TypeScript errors or runtime warnings. Where feasible, describe a test to write for the extracted module that exercises the domain logic with plain inputs and no mocks.
- **Progress** — Initialize with unchecked boxes for each milestone.
- **Surprises & Discoveries** — Initialize empty.
- **Decision Log** — Record your extraction choice and why you picked this concern over others.
- **Outcomes & Retrospective** — Initialize empty.
- **Idempotence and Recovery** — State that the extraction is additive (new file + modified imports) and can be reverted with a single git checkout.

After writing the file, tell the user: the ExecPlan is at `.agent/execplan-pending.md` and is ready to implement.

---

## Anti-Patterns to Avoid

- **Function-level nitpicking** — "This function has a fetch AND an if/else" is not what we're looking for. We want structural, flow-level entanglement.
- **Flagging clean orchestrators** — A controller that calls `validate(input)` then `db.save(result)` is doing its job. That's a boundary done right.
- **Flagging infrastructure-only code** — Migration scripts, seed files, config loaders, deploy scripts. These are pure infrastructure and don't contain domain logic.
- **Speculative findings** — Every finding must reference specific files and code paths. No "this area probably has issues."
- **Cosmetic concerns** — Code can be ugly and well-separated. Code can be clean and deeply entangled. Focus on the entanglement, not the aesthetics.
- **Offering choices** — Do not present multiple extraction options and ask the user to pick. You have the codebase and the scoring. Make the call.
- **Vague acceptance criteria** — Every criterion must be verifiable by running a command or checking a concrete property. No "code is cleaner" or "easier to maintain."
