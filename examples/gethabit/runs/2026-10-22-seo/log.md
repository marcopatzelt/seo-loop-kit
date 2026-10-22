# SEO loop run 2026-10-22-seo

Site https://gethabit.dev, market location_code 2840 / language_code en.

## 1. What was measured

DataForSEO, 7 calls (0 from cache). Data with parameters: `examples/gethabit/runs/2026-10-22-seo/data.md`.

- search volume: $0.0900
- serp: grill me skill: $0.0020
- serp: matt pocock skills: $0.0020
- serp: archify: $0.0020
- serp: ui ux pro max skill: $0.0020
- serp: taste skill: $0.0020
- ranked: gethabit.dev: $0.0120

Verify (step 08): nothing due

## 2. What changed since the last run

Tasks added: T-001. Board: `examples/gethabit/board.md`.

## 3. What was changed, file by file

### `examples/gethabit/content/archify.md` (T-001)

Gate, last attempt:

- PASS build passes: skipped: no build_command in config
- PASS title length: 47 chars, max 60
- PASS description length: 149 chars, max 155
- PASS no new noindex
- PASS keyword in title: "archify"
- PASS keyword in H1: "archify"
- PASS keyword in first paragraph: "archify"
- PASS no duplicate page

Critic: 17/20 (2 grading(s))

- Intent: add a short 'How to run it' section with the install command from the repo README, one example prompt and the output format, date-stamped and linked to the repo; the sentence 'We do not repeat them here because they change' leaves the main how-to question unanswered.
- Intent: consider retitling the H1/title toward the searcher, e.g. 'Archify: what it does, how to run it, when to use it', rather than leading with the site's loop angle.
- Own value: replace 'We have not tested Archify ourselves' with one worked example: run it on a small public repo before and after a structural PR and show or describe the diagram difference, which backs up the regenerate table.
- Copy: split the last sentence of 'Make it a habit' ('An Archify step would follow the same pattern: ...') into two shorter sentences.

## 4. Proposed, not changed

**Tasks created:** 1. It is `archify`, a new page at `/archify`. The search data shows 1,300 searches a month with low competition (DataForSEO, 2026-10-22). gethabit.dev ranks for nothing yet. The task is in `runs/2026-10-22-seo/tasks.json`.

**Page written:** `content/archify.md`, with `draft: true`.
- The title is 49 characters and the description is about 150, both within the limits.
- It links to the plan grill loop, UI taste loop and SEO loop pages.
- Every claim comes from the sources in the data file. The page does not describe features, install steps or performance, because the data file only has search-result titles for Archify. It points readers to the repo for those.
- The top 10 for Archify is a repo, a roadmap, a Reddit post, a video, a directory listing and a Medium post. This page adds a view on where a diagram fits in the plan-to-tickets habit.
- That habit angle is a suggestion, and the page says so. The critic may find the page thin because of the source limit.

**Skipped:**
- `grill me skill`, `matt pocock skills`, `ui ux pro max skill` and `taste skill` had no measured volume on 2026-10-22. I didn't create tasks for them.
- The gate found no existing page for `archify` or its slug, so that task went ahead.

## 5. What it cost

| Step | Model | Result | USD |
| --- | --- | --- | --- |
| build | claude-sonnet-5-5 | success | 0.0630 |
| critic | claude-opus-5-5 | success | 0.1180 |
| rewrite | claude-sonnet-5-5 | success | 0.0472 |
| critic | claude-opus-5-5 | success | 0.0958 |
| DataForSEO | | | 0.1120 |
| **Total** | | | **0.4361** |

Stop rule: not reached. Duration 2.3 min.
