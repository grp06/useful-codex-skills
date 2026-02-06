---
name: find-good-prs
description: >-
  Find high-value, low-risk PRs ready to merge in openclaw/openclaw.
  Use when looking for easy wins, safe PRs, or PRs with Greptile confidence 5/5.
---

Target: openclaw/openclaw

Fetch open PRs:
```sh
gh pr list --repo openclaw/openclaw --state open --json number,title,body,author,files,additions,deletions,reviewDecision,mergeable --limit 100
```

Filter criteria (all must pass):
1. Body contains `Confidence Score: 5/5` (Greptile)
2. No files in: `.github/`, `vitest.*.config.ts`, `apps/`, `Swabble/`
3. Title does NOT mention: CI, pipeline, build, workflow, action

Sweet spot (prioritize):
- **Docs only**: all files in `docs/` or `*.md` — near zero risk
- **Bug fix + tests**: title has "fix", includes `test/*.test.ts` or `src/**/*.test.ts`, <100 lines changed

Skip:
- iOS/Android/macOS changes (`apps/`, `Swabble/`)
- Extension changes (`extensions/`)
- UI changes (`ui/`)

Output per PR:
```
PR: https://github.com/openclaw/openclaw/pull/XXX
Title: "..."
Category: Docs only | Bug fix + tests
Diff: X files, +Y/-Z
Confidence: 5/5
Status: CI/Approved/Mergeable
Why: <1 sentence>
```

Sort: smallest diff first.
