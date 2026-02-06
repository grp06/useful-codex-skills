# useful-codex-skills

A small collection of Codex skills for planning, architecture, and GitHub PR workflows.

## Included skills

Planning / architecture
- `architecture-docs-creator`: Produces an `ARCHITECTURE.md` before implementation, capturing current structure and design intent.
- `update-architecture-docs`: Refreshes `ARCHITECTURE.md` after implementation so docs match the code.
- `execplan-create`: Turns a PRD/RFC/brief into a concrete step-by-step ExecPlan that is ready to execute.
- `implement-execplan`: Executes a pending ExecPlan from the `.agent` folder, step by step.
- `refactor-something`: Scans a repo and proposes a consolidation refactor that reduces surface area, then produces an ExecPlan for that change.
- `bead-creator`: Scans a repo and creates 3–5 Beads issues (via `br`) to seed a backlog, optionally focused on reliability/features/perf/security/docs/etc.

GitHub PR workflows
- `pr-review-r0`: Triage open PRs and identify which ones are junk / irrelevant.
- `pr-review-r1`: Summarize and sanity-check PR intent; catch duplicates or out-of-scope work early.
- `pr-review-r2`: Evaluate implementation simplicity and correctness.
- `pr-review-r3`: Identify risks/blockers and produce an actionable implementation plan.
- `pr-review-r4`: Implement the final plan and evaluate test coverage.
- `land-pr`: Land a PR end-to-end: temp rebase, full gate, merge, and thank the contributor.
- `find-good-prs`: Find high-value, low-risk PRs ready to merge (currently targeted at `openclaw/openclaw`).

## Usage
Each skill lives in its own folder and is documented in its `SKILL.md`.
Copy the folders you want into your Codex `skills/` directory.

## Using them together
1. Run `architecture-docs-creator` to establish a baseline `ARCHITECTURE.md`.
2. Use `execplan-create` for planned work, or `refactor-something` when you want a focused consolidation refactor.
3. Run `implement-execplan` to carry out the plan.
4. Finish with `update-architecture-docs` to sync docs with the final code.

## License
MIT
