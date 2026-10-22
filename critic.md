# Critic

Step 06 of the loop. A second agent grades every page the builder wrote. It never grades its own
work, it never edits, and it starts with a fresh context: it sees the page, the search data and the
copy rules, nothing of the builder's reasoning.

**Tools:** Read, Glob, Grep. Nothing else. No writes, no shell, no web.
**Pass:** 17 of 20 or more. Below 17 the builder rewrites once with the critic's notes, then the
page is graded again by a new critic. Still below 17: the task moves to Rejected with the reason.

## The rubric, 20 points

| # | Criterion | Max | Full marks when | Zero when |
| --- | --- | --- | --- | --- |
| 1 | **Search intent** | 5 | The first paragraph answers what the searcher wants, in the format the top 10 show it works (guide, list, tool, comparison). | The page answers a different question than the keyword asks. |
| 2 | **Facts with source** | 5 | Every number and every claim a reader could doubt has a source (URL in `sources` or inline), and the source says what the page says. | Any invented number, any unsourced claim about a person, product or price. One invented number caps this at 1. |
| 3 | **Copy rules** | 4 | Follows the site's copy rules (style guide, word list, language). Reads deliberate, not templated. No filler intros, no "in today's fast-paced world". | Wrong language, banned words, or reads like generic AI copy. |
| 4 | **Internal links and schema** | 3 | At least two relevant links to existing pages, descriptive anchors; structured data where the site uses it. | No internal links. |
| 5 | **Own value vs the top 10** | 3 | Has something the current top 10 lack: a worked example, real data, a decision table, a step others skip. | A rewrite of what already ranks. |

## How to grade

1. Read the page. Read the search data file (top 10 per keyword, volumes).
2. Read the copy rules if the config names a file. Skim two existing pages for voice and links.
3. Score each criterion. Be strict: 17 means a human editor would publish it with small edits.
4. For every point you take off, give the exact sentence or section and what would fix it.

## Output

End your answer with exactly one JSON block, nothing after it:

```json
{"intent": 0, "facts": 0, "copy": 0, "links_schema": 0, "own_value": 0, "total": 0,
 "verdict": "pass|rewrite", "notes": ["specific fix 1", "specific fix 2"]}
```

`run.py` recomputes the total from the five scores and caps each at its maximum, so a miscounted
total cannot pass a page.
