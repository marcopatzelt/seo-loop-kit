# seo-loop-kit

An SEO loop for coding agents. Every 21 days it reads a task board, pulls search data, writes one
page per finding, has each page checked by hard rules and graded by a second agent, and opens a
pull request. It finds work in the site's own Search Console data first: queries almost on page 1,
snippets nobody clicks, content gaps and pages losing clicks. 21 days after a page ships it reads Search Console again. If the page ranked but nobody
clicked, the task reopens on its own.

This is the open-source version of the loop Marco Patzelt runs on his own sites, entry #1 on
[Habit](https://gethabit.dev/loops/seo-loop). MIT licensed.

It is not an SEO tool. It is a habit: the loop never ships a page nobody checked, and it never
forgets a page it shipped.

## The three decisions

| | |
| --- | --- |
| **Trigger** | Every 21 days on a schedule (`routine.yml` for GitHub Actions, or a Claude Code routine), plus a manual run. |
| **Verification** | Before shipping: a hard gate in code (`gate.md`: build passes, title ≤ 60, description ≤ 155, no new noindex, keyword in title/H1/first paragraph, no duplicate page) and a critic with fresh context and read-only tools (`critic.md`, 20 points, pass at 17). After shipping: Search Console 21 days later (`verify.py`). |
| **Memory** | `board.md`: open, shipped (with dates), due for verify, rejected (with reasons). Plus one log per run and a data cache, so nothing is paid for twice. |

The steps, the permissions and the stop rule (3 tasks or $8 per run) are in [`LOOP.md`](LOOP.md).
That file is written for an agent: point Claude Code or Codex at it and it installs the loop.

## Install in 3 steps

1. **Copy.** `board.md` and `config.example.yaml` (as `config.yaml`) into `loops/seo-loop/`, the kit
   into `loops/seo-loop/kit/`, `routine.yml` into `.github/workflows/seo-loop.yml`. Or tell your agent:
   *"Read LOOP.md from seo-loop-kit and install this loop in my project. Show me the files first."*
2. **Configure.** In `config.yaml`: `site_url`, `content_dir`, `build_command`, one market
   (`location_code`, `language_code`) and your `target_keywords`. Set the keys in the environment
   (or as repository secrets): `ANTHROPIC_API_KEY`, `DATAFORSEO_LOGIN`, `DATAFORSEO_PASSWORD`, and
   for the 21-day check `GSC_KEY_FILE` (service account JSON, read-only scope, added to your Search
   Console property as a *Restricted* user).
3. **Test.** `python loops/seo-loop/kit/run.py --config loops/seo-loop/config.yaml --dry-run`.
   No model calls, no paid calls. Then one real run with a small budget: `--budget 3 --max-pages 1`.

Requirements: Python 3.10+, `pip install claude-agent-sdk google-auth requests`, and the Claude Code
CLI (which the Agent SDK drives).

## What is in here

| File | What it does |
| --- | --- |
| `LOOP.md` | The loop for an agent to install: decisions, steps 01 to 08, permissions, stop rule |
| `run.py` | One iteration with the Claude Agent SDK. Builder and critic are separate queries; the critic gets Read/Glob/Grep only. Writes only in the content dir and the run folder. Never pushes: it prints the git commands. Flags: `--dry-run`, `--budget`, `--model`, `--critic-model`, `--advisor`, `--max-pages`, `--draft-only` |
| `dfs.py` | DataForSEO client: search volume, keyword ideas, SERP top 10, ranked keywords. Per-run cost cap, cache folder, no retries, cost read from the response |
| `verify.py` | The 21-day check against Search Console (read-only), with the "ranked but no clicks" rule |
| `seoloop/opportunities.py` | Step 02 from Search Console: almost on page 1, seen but not clicked, content gaps, losing clicks |
| `board.md`, `gate.md`, `critic.md` | Board template, the hard checks, the 20-point rubric |
| `config.example.yaml` | Every setting with a comment |
| `routine.yml` | GitHub Actions: schedule + manual run, opens a PR with `gh` only if gate and critic passed |
| `seoloop/` | The pure parts (config, board, gate, budget), no network, fully tested |
| `examples/gethabit/` | A real run against gethabit.dev: board, data, one draft page, critic notes, run log, cost |
| `tests/` | `python -m unittest discover -s tests -t .` |

## Cost per run (measured 22 Oct 2026)

One real iteration against gethabit.dev (US market, 5 target keywords), 22 Oct 2026:

| Part | Cost |
|---|---|
| DataForSEO, 7 calls (search volume, 5 SERPs, ranked keywords) | $0.112 |
| Builder (Claude Sonnet) + critic, two gradings after one rewrite | $0.324 |
| **Total for one run, one page** | **$0.44** in 2.3 minutes |

The critic scored the first draft 14/20, the rewrite 17/20, so the page passed. A run with three tasks (the stop rule) costs roughly three times that. The budget cap stops a run at $8. Raw log: `examples/gethabit/runs/2026-10-22-seo/log.md`.

## Honest limits

- **It drafts, you publish.** Pages arrive as a pull request. Read them. The critic catches a lot,
  not everything, and it cannot check a claim against a source it cannot open (it has no web access).
- **Verification needs a live site with traffic.** A new domain gets no Search Console rows for
  weeks; then every page reopens as "invisible". That is correct, and not useful yet.
- **The 21-day rhythm is approximate on GitHub Actions.** Cron cannot say "every 21 days";
  `routine.yml` fires on day 1 and 22 and skips if the last run is younger than 20 days.
- **One market per config.** Running US and Germany means two configs, two boards. On purpose.
- **Markdown pages only out of the box.** For MDX, Astro or HTML, adapt `parse_page` in
  `seoloop/gate.py`. The gate is code so that you can.
- **"Build passes" is only as good as your build.** Without a `build_command` the check is recorded
  as skipped, never as passed.
- **Search Console is read, not inspected.** `verify.py` uses search analytics only; it does not call
  the URL Inspection API, so "not indexed" shows up as "no impressions".
- **Costs move with the model and the page.** The numbers above are one measured run, not a promise.
  The stop rule is the promise: a run ends at 3 tasks or $8.

## Where it comes from

The loop was built for one client site and one personal site, with DataForSEO for data, a board in
Markdown, and a critic with the same rubric. This kit is that loop with the site-specific parts
removed. The talk it was shown in calls the three parts Trigger, Verification and Memory; every loop
on Habit is described with those three.

## License

MIT, © 2026 Marco Patzelt. See `LICENSE`.
