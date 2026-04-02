# useful-codex-skills

A small collection of Codex skills for planning, architecture, and GitHub PR workflows.

## Included skills

Planning / architecture
- `session-analyzer`: Reconstruct repo-specific recent Codex workstreams from session logs and recommend the next best action.
- `tool-error-analyzer`: Reconstruct repo-scoped tool-call failures from rollout transcripts and recommend the next workflow/tooling improvements.
- `architecture-docs-creator`: Produces an `ARCHITECTURE.md` before implementation, capturing current structure and design intent.
- `update-architecture-docs`: Refreshes `ARCHITECTURE.md` after implementation so docs match the code.
- `execplan-create`: Turns a PRD/RFC/brief into a concrete step-by-step ExecPlan that is ready to execute.
- `execplan-improve`: Reads an existing ExecPlan, deeply analyzes every referenced file and code path, then rewrites the plan with concrete, code-grounded improvements.
- `implement-execplan`: Executes a pending ExecPlan from the `.agent` folder, step by step.
- `bead-creator`: Scans a repo and creates 3–5 Beads issues (via `br`) to seed a backlog, optionally focused on reliability/features/perf/security/docs/etc.

GitHub PR workflows
- `find-good-prs`: Find high-value, low-risk PRs ready to merge (currently targeted at `openclaw/openclaw`).
- `find-good-issues`: Find duplicate issues and hard + high-priority + high-severity issues worth triaging (openclaw/openclaw).
- `find-contributor-prs`: Find open PRs from top contributing authors, ordered by contributor rank (currently targeted at `openclaw/openclaw`).

## How to use
Each skill lives in its own folder and is documented in its `SKILL.md`.

Published skills are meant to live in this repo and be symlinked into `~/.codex/skills` with `publish.sh`, so edits here stay live in Codex without copy drift.

## Using them together
1. Run `architecture-docs-creator` to establish a baseline `ARCHITECTURE.md`.
2. Use `execplan-create` for planned work.
3. Run `execplan-improve` to audit and strengthen the plan before executing.
4. Run `implement-execplan` to carry out the plan.
5. Finish with `update-architecture-docs` to sync docs with the final code.
## License
MIT
