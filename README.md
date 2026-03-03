# useful-codex-skills

A small collection of Codex skills for planning, architecture, and GitHub PR workflows.

## Included skills

Planning / architecture
- `architecture-docs-creator`: Produces an `ARCHITECTURE.md` before implementation, capturing current structure and design intent.
- `update-architecture-docs`: Refreshes `ARCHITECTURE.md` after implementation so docs match the code.
- `execplan-create`: Turns a PRD/RFC/brief into a concrete step-by-step ExecPlan that is ready to execute.
- `execplan-improve`: Reads an existing ExecPlan, deeply analyzes every referenced file and code path, then rewrites the plan with concrete, code-grounded improvements.
- `implement-execplan`: Executes a pending ExecPlan from the `.agent` folder, step by step.
- `find-bug-generic`: Finds one highest-risk concrete defect and writes a focused ExecPlan under `.agent/potential-bugs/`.
- `refactor-something`: Scans a repo and proposes a consolidation refactor that reduces surface area, then produces an ExecPlan for that change.
- `find-entangled-flows`: Scans a codebase to find the single most meaningful entanglement where domain logic and infrastructure are coupled, then writes an ExecPlan to extract it.
- `bead-creator`: Scans a repo and creates 3–5 Beads issues (via `br`) to seed a backlog, optionally focused on reliability/features/perf/security/docs/etc.

GitHub PR workflows
- `find-good-prs`: Find high-value, low-risk PRs ready to merge (currently targeted at `openclaw/openclaw`).
- `find-good-issues`: Find duplicate issues and hard + high-priority + high-severity issues worth triaging (openclaw/openclaw).
- `find-contributor-prs`: Find open PRs from top contributing authors, ordered by contributor rank (currently targeted at `openclaw/openclaw`).

## How to use
Each skill lives in its own folder and is documented in its `SKILL.md`.

## Using them together
1. Run `architecture-docs-creator` to establish a baseline `ARCHITECTURE.md`.
2. Use `execplan-create` for planned work, `refactor-something` for a focused consolidation refactor, or `find-entangled-flows` to find the worst domain/infrastructure coupling.
3. Run `execplan-improve` to audit and strengthen the plan before executing.
4. Run `implement-execplan` to carry out the plan.
5. Finish with `update-architecture-docs` to sync docs with the final code.

## Find-Bug Pipeline Script

This repo also ships a simple orchestrator script that chains skills in a fresh worktree:

1. `find-bug-generic`
2. `execplan-improve`
3. `execplan-improve` (second pass)
4. `implement-execplan`

### One-time setup

```bash
cd ~/.codex/useful-codex-skills
./publish.sh find-bug-generic
./publish.sh --link-all
```

### Install repo-local wrapper

Run this inside any target repository:

```bash
~/.codex/useful-codex-skills/scripts/install-find-bug-wrapper.sh
```

This creates a local `./find-bug` wrapper and adds `find-bug` to `.git/info/exclude` so it stays untracked.

### Usage

From repo root:

```bash
./find-bug "look deeply into how we manage dependencies"
```

The script creates a new worktree from `origin/main`, runs the four stages above, keeps the worktree for inspection, and prints `run_id`, `worktree_dir`, `done_plan_path`, and `final_commit`.

## License
MIT
