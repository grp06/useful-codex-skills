# Teaching page structure

Use all nine sections. Keep the five-minute model understandable without opening implementation toggles.

## 1. Orientation

Include:

- Title: `<Change>: why it exists, how it works, and what it changes`.
- A one-sentence thesis.
- Three to five observable learning objectives.
- Reader paths: **Fast path** and **New to this system**.
- Change metadata: PR, commit, branch, comparison, related issue or design, and major subsystems when available.
- A compact glossary when unfamiliar terms are unavoidable.

The first screenful must establish the problem and why it matters.

## 2. Five-minute mental model

Use the running example to show the desired result, old result, gap, and central idea.

Include:

- A compact before-and-after diagram.
- The key invariant or contract in a callout.
- A small Changed / Unchanged comparison.
- One prediction question before revealing an important consequence.

## 3. Just-in-time background

Keep essential local background visible. Put deeper domain, architecture, or protocol prerequisites in clearly named toggles. Explain component responsibilities before asking the reader to reason about their interactions.

## 4. System before the change

Include:

- A system or boundary map.
- A step-by-step trace of the running example.
- Input, operation, and resulting state at each important step.
- The exact point where the old design becomes insufficient.
- The constraint that blocks an apparently simpler solution.

End with a self-explanation checkpoint and place its model answer in one toggle.

## 5. Core idea and new execution trace

Explain the smallest conceptual change before implementation details.

Include:

- The core idea in plain language.
- The new or revised invariant.
- A new trace using the same example.
- The contrasting or boundary case.
- What deliberately did not change.
- One prediction checkpoint.

Express each trace step as:

`input state -> operation -> output state -> purpose`

Use an analogy only when it preserves the important structure. Map each part to the actual system and state where the analogy stops applying.

## 6. Code walkthrough by subgoal

Begin with:

| Conceptual subgoal | Main code locations | Observable effect | Evidence |
|---|---|---|---|

For each subgoal, explain:

1. Purpose.
2. Relevant files, symbols, interfaces, or schemas.
3. Before-and-after structural difference.
4. Why the implementation supports the invariant.
5. What happens to the running example.
6. Boundary or edge case.
7. Test, execution result, documentation, or pinned link supporting the claim.

Use short excerpts that each illustrate one idea. Link to the full implementation instead of pasting large blocks.

## 7. Tests, boundaries, and tradeoffs

Explain:

- Behavior covered by tests and the regression or invariant each protects.
- Behavior intentionally left unchanged.
- Compatibility or migration concerns.
- Failure modes and degraded behavior.
- Performance, consistency, security, or operational implications.
- Author-documented alternatives.
- Inferred alternatives, clearly labeled as inference.
- Residual uncertainty or open questions.

For a refactor, show behavioral preservation. For a bug fix, connect the failing scenario to the regression test. For performance work, connect the workload to measurements or complexity. For security work, connect the threat path to the enforcement boundary and residual risk.

## 8. Synthesis

Reconstruct, in order:

1. Old model.
2. Motivating problem.
3. New mechanism.
4. Where it appears in code.
5. Most important tradeoff or boundary.

Add this teach-back prompt:

> Without looking back, explain the change in roughly one minute. Include the old failure mode, the new invariant, and the code boundary that enforces it.

Revisit and answer the initial prediction question.

## 9. Retrieval and transfer quiz

Create exactly five medium-difficulty questions that test the mental model rather than filenames, line numbers, or wording:

1. **Free recall:** explain the core problem or invariant.
2. **Prediction:** determine the behavior of a variation on the running example.
3. **Multiple choice:** distinguish the correct model from plausible misconceptions.
4. **Diagnosis:** infer the likely broken stage from a symptom, trace, or failed test.
5. **Transfer:** apply the design principle to a structurally related situation.

At least two questions must require the reader to generate an answer before seeing options. Use plausible, parallel distractors without gotchas. Use one answer toggle per question, including the correct answer, reasoning, misconception explanations where applicable, and code or test evidence.
