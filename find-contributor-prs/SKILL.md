---
name: find-contributor-prs
description: >-
  Find open PRs in openclaw/openclaw from top contributing authors.
  Use when looking for open PRs from known contributors, trusted authors,
  top contributors, or community PRs worth reviewing.
---

Target: openclaw/openclaw

## Contributors by Rank

Query authors in this exact order. Output must preserve this ordering.

1. steipete
2. vignesh07
3. sebslight
4. tyler6204
5. joshp123
6. gumadeiras
7. obviyus
8. mcinteerj
9. mukhtharcm
10. Glucksberg
11. roshanasingh4
12. Takhoffman
13. thewilloftheshadow
14. robbyczgw-cla
15. christianklotz
16. YuriNachos
17. dlauer
18. mbelinky
19. zerone0x
20. dbhurley
21. ngutman
22. Nachx639
23. petter-b
24. adam91holt
25. azade-c
26. bradleypriest
27. czekaj
28. lailoo
29. mneves75
30. pasogott
31. sfo2001
32. cash-echo-bot
33. grp06
34. jonisjongithub
35. quotentiroler
36. rubyrunsstuff
37. shakkernerd
38. sibbl
39. zknicker
40. AbhisekBasu1
41. ameno-
42. antons
43. bjesuiter
44. carlulsoe
45. conroywhitney
46. cpojer
47. dan-dr
48. danielz1z
49. dguido
50. dougvk

## Fetch Strategy

This repo has ~2500 open PRs. DO NOT bulk-fetch and filter client-side — it's too slow and `gh pr list --limit` caps at a fraction of the total.

Instead, query per-author. The `--author` flag filters server-side, so each call returns only that author's open PRs (typically 0–5). Run calls in parallel batches of 10 to stay within GitHub API rate limits.

Per-author query (use the exact rank order from the table above):

```sh
gh pr list --repo openclaw/openclaw --state open --author "USERNAME" --json number,author --limit 50
```

When running as an agent, make parallel Shell calls — batch ~10 authors per call to balance speed vs rate limits. Process authors rank 1–10 first, then 11–20, etc.

## Output

Print a flat list of PR links, grouped and ordered by author rank. Within each author, order by PR number ascending.

```
## #1 @steipete
- https://github.com/openclaw/openclaw/pull/1234
- https://github.com/openclaw/openclaw/pull/1567

## #2 @vignesh07
- https://github.com/openclaw/openclaw/pull/890

...
```

Skip authors with 0 open PRs (no heading, no mention).

End with a one-line total: `**X open PRs from Y contributors**`
