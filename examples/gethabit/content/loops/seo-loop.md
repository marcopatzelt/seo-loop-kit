---
title: "SEO loop: rank new pages every 21 days"
description: "Every 21 days the loop reads its task board, pulls search data, writes one page per finding, lets a second agent grade it, and opens a pull request."
keyword: "seo loop"
url: "/loops/seo-loop"
draft: false
---

# SEO loop

The SEO loop treats search as a habit, not a project. Every 21 days it reads its task board, pulls
search data, writes one page per finding, lets a second agent grade it, and opens a pull request.
Three weeks later it checks Search Console and reopens what did not work.

- Trigger: every 21 days (Claude Code routine or GitHub Actions)
- Verification: hard checks (build, title ≤ 60, description ≤ 155, no new noindex) and a critic at 17/20
- Memory: a task board
- Source: `marcopatzelt/seo-loop-kit`, MIT

Example stub for seo-loop-kit, condensed from the live entry at https://gethabit.dev/loops/seo-loop.
