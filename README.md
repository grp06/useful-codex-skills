# useful-codex-skills

A small collection of Codex skills for planning and architecture workflows.

## Included skills
- `refactor-something`: Scans a repo and proposes a consolidation refactor that reduces surface area, then produces an ExecPlan for that change.
- `execplan-create`: Turns a PRD/RFC/brief into a concrete step-by-step ExecPlan that is ready to execute.
- `implement-execplan`: Executes a pending ExecPlan from the `.agent` folder, step by step.
- `architecture-docs-creator`: Produces an `ARCHITECTURE.md` before implementation, capturing current structure and design intent.
- `update-architecture-docs`: Refreshes `ARCHITECTURE.md` after implementation so docs match the code.

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
