---
name: land-pr
description: >-
  Land a PR end-to-end: temp rebase, full gate, merge, and thank contributor.
  Use when asked to land a PR, merge a PR with rebase, or finalize a pull request.
---

Input
- PR: $1 (number or URL). If missing: use most recent PR in convo; if ambiguous: ask.

Goal
- End state: GitHub PR state = `MERGED` (never `CLOSED`).

0) Guardrails
- `git status -sb` clean (no local changes).
- If PR is draft, has conflicts, or you can't push to head branch: stop + ask.
- Prefer repo default branch as base (often `main`).

1) Capture PR context

```sh
PR="$1"
gh pr view "$PR" --json number,title,state,isDraft,mergeable,author,baseRefName,headRefName,headRepository,maintainerCanModify --jq '{number,title,state,isDraft,mergeable,author:.author.login,base:.baseRefName,head:.headRefName,headRepo:.headRepository.nameWithOwner,maintainerCanModify}'
prnum=$(gh pr view "$PR" --json number --jq .number)
contrib=$(gh pr view "$PR" --json author --jq .author.login)
base=$(gh pr view "$PR" --json baseRefName --jq .baseRefName)
head=$(gh pr view "$PR" --json headRefName --jq .headRefName)
head_repo_url=$(gh pr view "$PR" --json headRepository --jq .headRepository.url)
```

2) Update base + create temp branch

```sh
git checkout "$base"
git pull --ff-only
git checkout -b "temp/landpr-$prnum"
```

3) Checkout PR + rebase onto temp

```sh
gh pr checkout "$PR"
git rebase "temp/landpr-$prnum"
```

4) Changelog
- Update `CHANGELOG.md`: include `#$prnum` + thanks `@$contrib`.
- All code changes and tests should already be complete from prior review steps.

5) Gate (before commit)
- Run full repo gate (lint/typecheck/tests/docs). Example: `pnpm lint && pnpm build && pnpm test`.

6) Commit (via `committer`)

```sh
committer "fix: <summary> (#$prnum) (thanks @$contrib)" CHANGELOG.md <changed files>
land_sha=$(git rev-parse HEAD)
```

7) Push rebased PR branch (fork-safe)

```sh
git remote add prhead "$head_repo_url.git" 2>/dev/null || git remote set-url prhead "$head_repo_url.git"
git push --force-with-lease prhead "HEAD:$head"
```

8) Verify mergeable (abort if conflicts)

```sh
mergeable=$(gh pr view "$PR" --json mergeable --jq .mergeable)
if [ "$mergeable" != "MERGEABLE" ]; then
  echo "PR not mergeable ($mergeable). Base may have changed. Re-run land-pr."
  exit 1
fi
```

9) Merge PR
- Rebase: `gh pr merge "$PR" --rebase`
- Squash: `gh pr merge "$PR" --squash`
- Never `gh pr close`.

10) Sync base locally

```sh
git checkout "$base"
git pull --ff-only
```

11) Comment with SHAs + thanks

```sh
merge_sha=$(gh pr view "$PR" --json mergeCommit --jq '.mergeCommit.oid')
gh pr comment "$PR" --body "Landed via temp rebase onto $base.

- Gate: <cmds>
- Land commit: $land_sha
- Merge commit: $merge_sha

Thanks @$contrib!"
```

12) Verify state == `MERGED`

```sh
gh pr view "$PR" --json state,mergedAt --jq '.state + \" @ \" + .mergedAt'
```

13) Cleanup

```sh
git branch -D "temp/landpr-$prnum"
```
