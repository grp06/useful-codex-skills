# useful-codex-skills

A small collection of Codex skills for goals, planning, and execution.

## Included skills

Planning / architecture
- `goalcraft`: Turn a rough draft, vague ambition, or messy task brief into an evidence-checked Codex `/goal` objective.
- `execplan-create`: Turn a decided refactor, PRD, RFC, or detailed brief into an ExecPlan inside a work-item directory.
- `execplan-improve`: Read an existing ExecPlan, analyze the referenced code paths, and rewrite the plan with concrete, code-grounded improvements.
- `implement-execplan`: Execute a work-item ExecPlan or legacy singleton plan while tracking implementation state explicitly.

## How to use

Each skill lives in its own folder and is documented in its `SKILL.md`.

Published skills are meant to live in this repo and be symlinked into `~/.codex/skills` with `publish.sh`, so edits here stay live in Codex without copy drift.

## Planning Workflow

1. Run `goalcraft` when a durable objective needs a compact, evidence-checked `/goal` contract.
2. Run `execplan-create` to write `execplan.md` for a decided refactor, PRD, RFC, or detailed brief.
3. Run `execplan-improve` to audit and strengthen the plan before executing.
4. Run `implement-execplan` to carry out the plan while updating work-item lifecycle metadata instead of moving files to `done/`.
5. Review the implementation against the decision rationale and the ExecPlan.

## License

MIT
