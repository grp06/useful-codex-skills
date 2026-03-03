---
name: find-bug-generic
description: >-
  Explore a codebase to find the highest-risk bug — a real defect, not a style issue. Writes an ExecPlan to .agent/potential-bugs/<descriptive-name>.md.
  Use when user asks to find bugs, hunt for the worst bug, or surface the most dangerous defect in any project.
---

# Find the Highest-Risk Bug

Explore the codebase and identify **one** real bug most likely to cause user-visible harm: wrong outputs, lost data, silent failures, corrupted state, or incorrect logic. Style issues and hypothetical risks don't count.

Be decisive. Read the code, state assumptions, pick one, and justify it.

## Output

Write an ExecPlan to `.agent/potential-bugs/<chosen-name>.md`. Use PLANS.md from the repo or `$CODEX_HOME/skills/execplan-create/PLANS.md`. The plan must be self-contained — include a regression test that fails before and passes after the fix.

**Worktree handling:** If you are in a git worktree, write to `.agent/potential-bugs/` in the **current working tree** by default. Only target the main worktree when the user explicitly asks for it.

If you also implement the fix in the same workflow, do not leave the finished plan in `.agent/potential-bugs/`. After implementation + validation are complete, rename and move it to `.agent/done/<chosen-name>-implemented-YYYYMMDD.md` (create `.agent/done/` if missing) in the same working tree where implementation happened.

Tell the user the path when done.
