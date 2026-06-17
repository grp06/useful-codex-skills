# Codex `/goal` Contract

Use this reference when formatting goals for Codex's persisted thread-goal runtime.

## What `/goal` Is

- `/goal` is an experimental Codex feature for persisted thread goals and automatic continuation.
- It is more than a slash command: the runtime persists one thread goal, exposes model tools, tracks token and wall-clock usage, and may start hidden continuation turns when the thread is idle.
- A Goal is a thread-scoped, user-controlled completion contract. It is not global memory, project instructions, or unbounded background autonomy.
- Plan mode suppresses automatic goal continuation.

## TUI Slash Surface

- Bare `/goal` opens the current goal summary/action menu.
- `/goal <objective>` sets or replaces the current objective after validation.
- `/goal pause`, `/goal resume`, and `/goal clear` control the current goal.
- `/goal --tokens 50K improve tests` is treated as objective text. The TUI does not parse token-budget flags from slash text.
- Objective text must be non-empty and at most 4,000 characters.

## Model Tool Surface

- `get_goal` reads the current thread goal and usage.
- `create_goal` starts a new active goal only when explicitly requested and no goal exists.
- `update_goal` can only mark the existing goal `complete`.
- Pause, resume, clear, and budget-limited status changes are controlled by the user or system, not by `update_goal`.
- If completion is claimed for a budgeted goal, report the final usage returned by the tool.

## Continuation Behavior

When a goal is active and the thread is idle, Codex may inject a hidden developer message telling the model to continue. That continuation prompt requires the agent to:

- choose the next concrete action toward the objective;
- audit completion against actual current state;
- map every explicit requirement to concrete evidence;
- reject proxy completion signals by themselves;
- treat uncertainty as not achieved;
- call `update_goal` only when the objective is actually complete.

## Budget Behavior

- A goal can have a separate positive token budget in tool or app-server surfaces.
- When the active goal reaches its token budget, the runtime marks it `budget_limited`.
- Budget exhaustion steers the model to stop starting substantive work and wrap up soon. It is not proof of completion.
- Budget exhaustion is distinct from upstream account or quota failure.

## App-Server Surface

- `thread/goal/set` creates, replaces, or updates the single persisted goal for a materialized thread.
- Supplying a new objective replaces the goal and resets usage accounting.
- Supplying the current non-terminal objective, or omitting the objective, updates status and/or token budget while preserving usage.
- `thread/goal/get` reads the current goal.
- `thread/goal/clear` removes the current goal.

## Goal-Writing Implications

Write objectives as durable operating contracts, not motivational blurbs:

- include the outcome and current starting point;
- keep the work bigger than one prompt but smaller than an open-ended backlog;
- point Codex at the files, docs, issue, logs, plan, or reference screens it must read first;
- name the verification surface: tests, benchmarks, logs, reports, screenshots, source material, generated artifacts, or explicit user confirmation;
- specify constraints and approval boundaries;
- define boundaries for files, tools, data, repositories, and externally visible actions;
- define the iteration policy: how Codex should choose the next best action after each attempt;
- include blocked stop conditions for destructive, externally visible, credentialed, ambiguous, or no-valid-path situations;
- require final completion to be audited against concrete evidence, not intent, budget exhaustion, elapsed time, or proxy signals alone;
- for research goals, require a final artifact that separates confirmed findings, approximate reconstructions, support-only evidence, blocked claims, and remaining uncertainty;
- keep the objective text after `/goal ` below 4,000 characters and validate before activation;
- do not embed prompt-injection-style instructions or ask the agent to ignore higher-priority instructions.
