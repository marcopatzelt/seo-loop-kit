# SEO loop

You are an agent installing this loop in a project. Read this file to the end, show the person the
files you will create, and only then create them. Change nothing outside the paths listed under
Permissions.

The loop in one sentence: every 21 days it reads its task board, pulls search data, writes one
page per finding, has the page checked by hard rules and graded by a second agent, and opens a pull
request. Three weeks after a page ships it reads Search Console and reopens the page if it did not
work.

## The three decisions

Every loop is three decisions. These are this loop's.

| Decision | This loop | Where it lives |
| --- | --- | --- |
| **Trigger**: what starts a run | Every 21 days on a schedule. Nobody presses go. | `routine.yml` (GitHub Actions) or a Claude Code routine |
| **Verification**: how a run knows its work is good | Twice. Before shipping: a hard gate (`gate.md`) and a second agent with fresh context that grades the page out of 20 (`critic.md`, pass at 17). After shipping: Search Console 21 days later (`verify.py`). | `seoloop/gate.py`, `critic.md`, `verify.py` |
| **Memory**: what survives the run | A task board: what is open, what shipped and when, what is due for its check, what was rejected and why. Every run reads it first. | `loops/seo-loop/board.md`, plus `runs/<date>/log.md` and the data cache |

## The steps

```
01 check board → 02 analyze → 03 create tasks → 04 gate → 05 build → 06 critic → 07 ship as PR
       ↑                                                                               │
       └──────────────────────── 08 verify after 21 days ←─────────────────────────────┘
```

**01 Check the board.** Read `board.md`. Shipped tasks whose `verify:` date has come move to *Due for
verify*. Open tasks are the first candidates. Do not re-measure what was measured last run unless you
say why.

**08 Verify after 21 days** (runs right after 01, so old work is judged before new work starts).
For each task due: clicks, impressions, CTR and average position for the page over the 21 days
after it shipped, from Search Console. Rules:

- Position ≤ 10, ≥ 100 impressions, CTR < 0.5 %: **ranked, but nobody clicked**. The task reopens
  as type `snippet` (rewrite title and description).
- Fewer than 50 impressions and position > 30, or no data: reopens as `improve`.
- Clicks > 0 or position ≤ 10: `verified`, the numbers go on the board.

**02 Analyze.** Two sources. First the site's own searches from Search Console (free, last 28 days
against the 28 before, `seoloop/opportunities.py`): queries where a page ranks 8-20 (**improve**),
top-10 queries with many impressions and a click rate under 1 % (**snippet**), queries with
impressions but no page that fits, the content gaps (**new-page**), and pages with 30 % fewer
clicks than before (**refresh**). Then, for the target keywords, DataForSEO in one market (location
and language fixed in the config, never mixed): search volume, the Google top 10 and its features,
and what the site already ranks for. Every call goes through a cache, so the same question is never
paid twice. An empty result is data: record it, do not replace it with a neighbouring number.

**03 Create tasks.** One task per finding: keyword, numbers with source and date, target path,
hypothesis, and the metric that will be checked in 21 days. Skip what the board already has.
At most 3 tasks per run. "Nothing worth doing, here are the numbers" is a valid run.

**04 Gate.** Before writing: if a page for that keyword already exists or the task is a duplicate,
stop here. After writing: the hard checks in `gate.md` (build passes, title ≤ 60, description ≤ 155,
no new noindex, keyword in title, H1 and first paragraph, no duplicate page). One fix attempt, then
the task is rejected with the failing checks as the reason.

**05 Build.** Write the page into the content directory only: frontmatter with title, description,
keyword and sources; an H1; a first paragraph that answers the search; internal links to at least
two existing pages. No invented numbers. No layout, component or config changes.

**06 Critic.** A second agent with fresh context and read-only tools grades the page with the
rubric in `critic.md`: search intent 5, facts with source 5, copy rules 4, internal links and schema
3, own value against the top 10 3. Pass at 17 of 20. Below 17 the builder rewrites once with the
critic's notes and a new critic grades again. Still below 17: rejected, with the score and reason.

**07 Ship as PR.** Commit the passed pages, the board and the run folder on a branch
`seo-loop/<date>` and open a pull request. A human merges. The loop never merges, never deploys and
never pushes to the main branch. The task moves to *Shipped* with `shipped:` and `verify:` (+21
days). If the merge happens later, set `shipped:` to the merge date.

Every run ends with `runs/<date>/log.md`: what was measured (with parameters), what changed since
last run, what was changed file by file, what was proposed but not changed, and what it cost.

## Permissions

| | |
| --- | --- |
| **Writes** | the content directory from the config (pages), `loops/seo-loop/**` (board, runs, cache) |
| **Reads** | the project, except `.env*`, `secrets/`, keys and credentials |
| **Network** | `api.dataforseo.com`, `searchconsole.googleapis.com` / `www.googleapis.com` (read-only scope), the model API |
| **Sends** | nothing. No email, no posts, no messages |
| **Git** | creates a branch and a pull request. Never merges, never pushes to main |
| **Human** | merges every PR. Owns visible copy: the loop proposes, the human decides |
| **Keys** | only from the environment: `ANTHROPIC_API_KEY`, `DATAFORSEO_LOGIN`, `DATAFORSEO_PASSWORD`, `GSC_KEY_FILE`. Never in files, never printed |

## Stop rule

A run stops after **3 tasks or $8**, whichever comes first (model plus data). DataForSEO has its own
cap per run (`budget.dataforseo_cap_usd`, default $0.50). When a limit is hit the run still writes
its board and log, and says which limit stopped it.

## Install

1. Copy into the project:
   - `loops/seo-loop/board.md` from `board.md`
   - `loops/seo-loop/config.yaml` from `config.example.yaml`: set `site_url`, `content_dir`,
     `build_command`, market (`location_code`, `language_code`) and 5 to 40 `target_keywords`.
   - the kit itself (`run.py`, `dfs.py`, `verify.py`, `seoloop/`, `prompts/`, `critic.md`) into
     `loops/seo-loop/kit/` or install it as a package.
   - `.github/workflows/seo-loop.yml` from `routine.yml`.
2. Set the secrets in the CI or shell environment: `ANTHROPIC_API_KEY`, `DATAFORSEO_LOGIN`,
   `DATAFORSEO_PASSWORD`, and for step 08 `GSC_KEY_FILE` (path to a Search Console service account
   key with read-only scope, added to the property as a *Restricted* user).
3. Test it: `python loops/seo-loop/kit/run.py --config loops/seo-loop/config.yaml --dry-run`. No
   model calls, no paid calls; it prints what a run would do.

When done, end your answer with exactly this line, filled in for this project:

```
↻ Loop installed. Trigger: every 21 days (.github/workflows/seo-loop.yml, plus manual run). Verification: hard gate + critic ≥ 17/20 before the PR, Search Console 21 days after. Memory: loops/seo-loop/board.md. Test it: python loops/seo-loop/kit/run.py --config loops/seo-loop/config.yaml --dry-run. Undo: delete loops/seo-loop/ and .github/workflows/seo-loop.yml.
```
