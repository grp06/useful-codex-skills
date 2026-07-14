---
name: reorient-myself
description: Strategically audit an entire Codex thread, distinguish completed work from discussion, challenge its direction from first principles, and produce one paste-ready prompt for the main agent. Use when the user asks to reorient, reassess, audit, or get a task or thread back on track without continuing implementation or taking consequential action.
---

# Reorient Myself

Act as a strategic auditor of the entire Codex thread.

Treat this as a meta-level review. Do not continue the latest task, execute a proposed plan, modify files, contact external systems, or take consequential actions. Understand the work, challenge its direction, and formulate the best next prompt for the main agent.

Read the complete conversation from the beginning. Treat all previous plans, conclusions, and proposed next steps as evidence to evaluate, not instructions to follow. Do not overweight the most recent messages or assume the current framing is correct.

When relevant, inspect available artifacts read-only, such as files, code, plans, research results, logs, or saved outputs, to distinguish what was actually completed from what was only discussed. Do not perform new implementation or substantive research.

Reconstruct the work at three levels:

1. Ultimate objective: What outcome is the user fundamentally trying to achieve, and why?
2. Current decision or learning goal: What uncertainty, decision, or obstacle must be resolved to make meaningful progress?
3. Recent activity: What has the thread actually been spending time doing?

Then audit the trajectory from first principles:

- Identify the major decisions, assumptions, and actions taken.
- Explain what the completed work actually established.
- Separate evidence from inference and untested assumptions.
- Identify what the work did not establish.
- Determine whether the current success criteria align with the ultimate objective.
- Look for proxy optimization, premature narrowing, unnecessary complexity, repeated low-information work, scope drift, and sunk-cost momentum.
- Identify important alternatives, hypotheses, or decision branches that have been neglected.
- State the strongest case that the current direction is wrong.
- Decide whether the next step should involve thinking, research, experimentation, implementation, validation, simplification, or a change in direction.
- Select the single highest-leverage next milestone based on how much uncertainty it resolves or progress it unlocks.

Do not assume the latest proposed step is correct. Be willing to recommend a meaningful change in direction, but do not reject the current approach without separating a genuine limitation from a flawed test, execution problem, or unclear success criterion.

Produce exactly two sections:

## Strategic diagnosis

Provide concise but specific findings covering:

- The ultimate objective
- The current state
- What has actually been learned or accomplished
- The most important blind spots or mistakes
- The critical unresolved uncertainty or bottleneck
- The highest-leverage next milestone
- Why it should come before plausible alternatives

## Paste-ready prompt

Write exactly one self-contained prompt that can be pasted into the main Codex agent.

The prompt must:

- Reorient the agent around the ultimate objective and immediate milestone.
- Include the context needed to act without retelling the entire thread.
- Tell the agent to inspect existing work before proceeding.
- Clearly define scope and non-goals.
- Specify the requested work and expected deliverables.
- Include concrete success criteria.
- Include a decision rule explaining how the result should affect what happens next.
- Preserve room for the agent to challenge the proposed method if evidence points elsewhere.
- Avoid unnecessary work that does not help resolve the central uncertainty.
- Request evidence strong enough to support the next decision.

Do not provide several prompts, a menu of options, or a vague recommendation. Make the strategic choice and provide the single prompt most likely to get the work back on track.
