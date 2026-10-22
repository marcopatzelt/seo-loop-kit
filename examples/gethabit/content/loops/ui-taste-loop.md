---
title: "UI taste loop: keep every UI change on taste"
description: "Every PR that touches UI files is built with frontend design and taste, screenshotted at three widths and graded by a separate impeccable audit."
keyword: "ui taste loop"
url: "/loops/ui-taste-loop"
draft: false
---

# UI taste loop

The UI taste loop makes a design check the default for every pull request that touches UI files.
The change is built with frontend design and taste, screenshotted at 1440, 768 and 375 pixels, and
graded by a separate impeccable audit. Rejected patterns go on a design board so the next run avoids them.

- Trigger: a PR changes UI files (GitHub Actions)
- Verification: screenshots, no console errors, build passes, critic at 17/20 or more
- Memory: `design-board.md`
- Built from: `anthropics/frontend-design` (Apache-2.0), `leonxlnx/taste-skill` (MIT), `pbakaus/impeccable` (critic, Apache-2.0)

Example stub for seo-loop-kit, condensed from the live entry at https://gethabit.dev/loops/ui-taste-loop.
