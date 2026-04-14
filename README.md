# useful-codex-skills

A small collection of Codex skills for planning and refactors.

## Included skills

Planning / architecture
- `find-refactor-candidates`: Search a repo for the top materially different refactor opportunities and create a candidate work item without committing yet.
- `select-refactor`: Pressure-test the shortlist, gather cheap repo evidence, and lock the final refactor decision before planning.
- `execplan-create`: Turn a decided refactor, PRD, RFC, or detailed brief into an ExecPlan inside a work-item directory.
- `execplan-improve`: Read an existing ExecPlan, analyze the referenced code paths, and rewrite the plan with concrete, code-grounded improvements.
- `implement-execplan`: Execute a work-item ExecPlan or legacy singleton plan while tracking implementation state explicitly.

## How to use

Each skill lives in its own folder and is documented in its `SKILL.md`.

Published skills are meant to live in this repo and be symlinked into `~/.codex/skills` with `publish.sh`, so edits here stay live in Codex without copy drift.

## Refactor Workflow

1. Run `find-refactor-candidates` to create a work item under `.agent/work/<id-slug>/` with `meta.json` and `candidates.md`.
2. Run `select-refactor` to challenge the shortlist and write `decision.md`.
3. Run `execplan-create` to write `execplan.md` inside the same work item.
4. Run `execplan-improve` to audit and strengthen the plan before executing.
5. Run `implement-execplan` to carry out the plan while updating work-item lifecycle metadata instead of moving files to `done/`.
6. Run `review-recent-work` to review the implementation against both the decision rationale and the ExecPlan.

## License

MIT
