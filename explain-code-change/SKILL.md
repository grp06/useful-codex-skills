---
name: explain-code-change
description: Investigate a code change, diff, commit, branch, or pull request and create a learning-oriented Notion page that teaches why the change exists, how it works, and how to reason about related cases. Use when the user wants a verified before-and-after mental model rather than a surface-level diff summary.
---

# Explain Code Change

Create a Notion page that helps the reader understand, retain, and apply a code change. Teach a causal model the reader can use to predict behavior, not merely a summary of edited lines.

Before drafting or publishing, read:

- [references/page-structure.md](references/page-structure.md) for the required teaching-page structure.
- [references/notion-publishing.md](references/notion-publishing.md) for connector setup, destination selection, privacy, formatting, and verification.

## Definition of success

After reading the page, the reader should be able to:

1. Explain the problem, requirement, or constraint that motivated the change.
2. Trace a representative input through the system before and after the change.
3. Connect each stage of that trace to the corresponding code and tests.
4. State the important invariants, boundaries, edge cases, and tradeoffs.
5. Predict what will happen in a novel but structurally related case.

Generate three to five change-specific learning objectives with observable verbs such as explain, trace, predict, compare, diagnose, or justify.

Default to a technically strong programmer who is unfamiliar with this part of the repository. Adapt when the user supplies another audience. Scale depth with conceptual complexity and risk, not changed-line count.

## Investigate before writing

Do not draft the page until you can answer:

- What observable problem, limitation, or capability motivated the change?
- What did the relevant system do before the change?
- Where did the old behavior become incorrect, insufficient, expensive, or difficult to maintain?
- What is the smallest conceptual idea introduced by the change?
- Which contract or invariant changed, and which important invariants remained the same?
- How does one concrete input move through the old and new systems?
- Which files, symbols, tests, issues, or design documents support each important claim?
- What novel case would distinguish genuine understanding from memorization?

To answer them:

1. Read the complete diff.
2. Read the PR, commit message, issue, design document, or discussion when available.
3. Inspect the definitions of changed symbols.
4. Trace relevant callers and callees.
5. Inspect associated data structures, schemas, state, configuration, persistence, API boundaries, and tests.
6. Explore beyond the changed code when necessary to explain observable behavior.
7. Stop expanding scope when more code no longer changes the causal explanation, relevant boundary, or reader prediction ability.
8. Run the smallest relevant tests or reproduce a representative example when execution tools are available.

Maintain an internal evidence map:

`claim -> file, symbol, test, execution result, or design source`

Prefer commit-pinned links over mutable branch links.

Classify important claims as:

- **Verified behavior:** supported directly by code, tests, execution, or documentation.
- **Documented intent:** stated in a PR, issue, commit, or design document.
- **Inference:** a reasonable interpretation not explicitly documented.
- **Unknown:** not established by available evidence.

Never present inference as author intent. Do not narrate the repository exploration process in the final page.

## Build the mental model

### Use one running example

Choose a small, realistic example that crosses the most important changed path. Carry the same data through the motivating problem, old system, new system, diagrams, code walkthrough, and at least one quiz question.

Add one contrasting or boundary case that differs in one important dimension. Use it to expose an invariant, branch condition, or limitation that the main example obscures.

### Move from concrete to mechanism to code

Use this progression:

1. Concrete scenario and observable behavior.
2. Relevant system model.
3. Core mechanism or invariant.
4. Worked execution trace.
5. Mapping from conceptual steps to implementation.
6. Application to edge cases and novel situations.

Include background only when removing it would make the reader less able to explain or predict the change.

### Use progressive disclosure

Provide two reading paths:

- **Five-minute model:** problem, central idea, before-and-after behavior, and key invariant.
- **Deep dive:** prerequisites, execution traces, implementation, tests, edge cases, and tradeoffs.

Keep the causal explanation visible. Use toggles for optional prerequisites, lengthy implementation detail, supporting evidence, and quiz answers.

### Make the reader predict

Use two to four brief, consequential checkpoints. Ask the reader to predict an outcome or enforcement boundary before revealing the answer in a toggle.

### Use diagrams purposefully

Prefer a small set of consistent diagram families:

1. Static system map for components, ownership, and boundaries.
2. Dynamic trace for control flow, data flow, sequence, or state transition.
3. Before-and-after comparison only when the first two cannot convey the distinction.

Every diagram must answer a named question, reuse prose and code labels, include concrete example data when useful, omit decorative detail, and end with a one-sentence takeaway. Use a table or compact text diagram when rendering would be unreliable.

### Group implementation by conceptual subgoal

Explain changes in causal or runtime order, not file order. Use action-oriented subgoals such as:

- Establish the request context.
- Resolve the effective configuration.
- Preserve state across the asynchronous boundary.
- Validate the new invariant.
- Expose the result through the public API.

Reuse the same subgoal labels in the execution trace, code headings, and synthesis.

## Complete the page

Follow [references/page-structure.md](references/page-structure.md) exactly enough that every required section and quiz type is present, while adapting depth to the change.

Follow [references/notion-publishing.md](references/notion-publishing.md) before making any Notion write. Treat destination and privacy verification as part of the completion contract.

Before reporting completion, verify:

- The causal explanation is supported by the evidence map.
- The running example remains consistent throughout.
- Essential facts are not hidden in toggles.
- Code excerpts are short and each teach one idea.
- The page contains exactly five medium-difficulty retrieval and transfer questions.
- The created page was fetched and checked for title, section structure, toggles, tables, links, quiz numbering, and destination.
- Any incomplete verification, inference, or residual uncertainty is stated explicitly.
