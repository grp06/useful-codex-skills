---
name: pr-review-r4
description: >-
  Implement the final plan and evaluate test coverage.
  Use when applying PR changes or reviewing test coverage for a PR.
---

Implement the final plan: apply code changes, update docs/types as needed, and ensure the PR is consistent and clean. Do not update changelogs (land-pr handles that).

Review all diffs and evaluate test coverage against intended behavior and edge cases. Add any missing tests needed to confidently validate this PR (including regressions). Be specific about what each test proves.

Do not run tests now (land-pr runs the full gate before merge).

Do not ask for feedback or clarification. Be decisive. If anything is ambiguous, state your interpretation and proceed.
