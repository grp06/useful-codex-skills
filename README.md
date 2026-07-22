# useful-codex-skills

A small collection of Codex skills for goals, planning, execution, and code understanding.

## Included skills

Planning / execution chain
- `grill-me`: Pressure-test a plan or design through a focused decision-tree interview.
- `grillcraft`: Compile a completed grilling session into `decision.md`, an improved ExecPlan, and a Goalcraft execution goal.
- `execplan-create`: Turn a decided refactor, PRD, RFC, or detailed brief into an ExecPlan inside a work-item directory.
- `execplan-improve`: Read an existing ExecPlan, analyze the referenced code paths, and rewrite the plan with concrete, code-grounded improvements.
- `implement-execplan`: Execute a work-item ExecPlan or legacy singleton plan while tracking implementation state explicitly.
- `review-recent-work`: Review the latest implemented work item or completed ExecPlan, fix obvious issues, and record the result.

Goal support
- `goalcraft`: Turn a rough draft, vague ambition, or messy task brief into an evidence-checked Codex `/goal` objective.

Strategic review
- `reorient-myself`: Audit a Codex task from first principles and produce one paste-ready prompt to get it back on track.

Code understanding
- `explain-code-change`: Investigate a diff, commit, branch, or pull request and publish a verified, learning-oriented explanation to the user's connected Notion workspace.

## How to use

Each skill lives in its own folder and is documented in its `SKILL.md`.

Skills that declare MCP dependencies, such as `explain-code-change`, require the user to connect and authenticate the corresponding integration before use.

Published skills are meant to live in this repo and be symlinked into `~/.codex/skills` with `publish.sh`, so edits here stay live in Codex without copy drift.

## Planning Workflow

These skills are typically chained in this order:

1. Run `grill-me` to pressure-test the plan or design before turning it into execution work.
2. Run `grillcraft` to turn the completed grill into a work-item `decision.md`, create and improve `execplan.md`, and activate a Goalcraft execution goal.
3. Run `review-recent-work` after implementation when you want a fresh manual review pass.

Use `execplan-create`, `execplan-improve`, and `implement-execplan` directly when you want the lower-level manual workflow instead of the GrillCraft handoff. Use `goalcraft` separately when a durable objective needs a compact, evidence-checked `/goal` contract.

Use `reorient-myself` when a task needs a strategic reset before more planning or implementation.

## License

MIT
