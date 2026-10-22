#!/usr/bin/env python3
"""One iteration of the SEO loop, run with the Claude Agent SDK.

  python run.py --config loops/seo-loop/config.yaml [--dry-run] [--budget 8] [--model claude-sonnet-5-5]
                [--critic-model claude-opus-5-5] [--advisor claude-fable-5-1] [--max-pages 3] [--draft-only]

Steps (LOOP.md): 01 board -> 02 analyze -> 03 tasks -> 04 gate -> 05 build -> 06 critic -> 07 ship as PR
(commands printed, never run) -> 08 verify after 21 days (verify.py, when pages are due).

Hard limits:
- Writes only inside the content dir and this run's folder. Python writes board.md and the logs.
- The critic is a separate query with Read/Glob/Grep only.
- Stops after max_tasks or max_usd (model + DataForSEO), whichever comes first.
- Never pushes, never opens anything on GitHub. Prints the git commands for a PR branch.
- Keys only from the environment (ANTHROPIC_API_KEY, DATAFORSEO_LOGIN/PASSWORD, GSC_KEY_FILE). Never printed.
--dry-run makes no model calls and no paid calls: it reads the cache and prints the plan.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

KIT = Path(__file__).resolve().parent
sys.path.insert(0, str(KIT))
import dfs as dfsmod  # noqa: E402
from seoloop import gate  # noqa: E402
from seoloop.board import Board, norm  # noqa: E402
from seoloop.budget import RunBudget  # noqa: E402
from seoloop.config import load_config  # noqa: E402

SECRET = re.compile(r"(^|/)\.env|secret|credential|\.pem$|\.key$|id_rsa|/\.ssh/|gsc.*\.json$|service.?account", re.I)
CRITIC_MAX = {"intent": 5, "facts": 5, "copy": 4, "links_schema": 3, "own_value": 3}
CRITIC_RESERVE_USD = 0.8  # kept back per page so the critic can always run


# ---------------------------------------------------------------- permissions
def under(p: Path, roots) -> bool:
    return any(p == r or r in p.parents for r in roots)


def make_guard(read_roots, write_roots):
    """can_use_tool callback: reads under read_roots, writes under write_roots, secrets never."""
    from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny
    read_roots = [Path(r).resolve() for r in read_roots]
    write_roots = [Path(r).resolve() for r in write_roots]

    async def guard(tool, args, _ctx):
        raw = args.get("file_path") or args.get("path") or ""
        p = Path(raw or read_roots[0]).expanduser()
        p = (read_roots[0] / p if not p.is_absolute() else p).resolve()
        if SECRET.search(str(p)):
            return PermissionResultDeny(message="Secret files are blocked.")
        if tool in ("Read", "Glob", "Grep") and under(p, read_roots + write_roots):
            return PermissionResultAllow()
        if tool in ("Write", "Edit") and under(p, write_roots):
            return PermissionResultAllow()
        return PermissionResultDeny(message=f"Not allowed: {tool} {raw}. Writes only under "
                                            f"{', '.join(map(str, write_roots)) or 'nothing (read-only)'}.")
    return guard


# ---------------------------------------------------------------- model calls
async def ask(prompt: str, *, model: str, budget_usd: float, tools: list, guard, cwd: Path,
              system: str | None = None, advisor: str = "", label: str = "") -> dict:
    from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock,
                                  ToolUseBlock, query)
    env = {"CLAUDE_CODE_OAUTH_TOKEN": ""}
    if os.environ.get("ANTHROPIC_API_KEY"):
        env["ANTHROPIC_API_KEY"] = os.environ["ANTHROPIC_API_KEY"]
    opt = ClaudeAgentOptions(model=model, max_budget_usd=max(0.05, budget_usd), max_turns=80,
                             setting_sources=[], env=env, cwd=str(cwd), tools=tools,
                             can_use_tool=guard, system_prompt=system,
                             extra_args={"advisor": advisor} if advisor else {})

    async def stream():
        yield {"type": "user", "message": {"role": "user", "content": prompt}}

    text, out = [], {"cost_usd": 0.0, "subtype": "none", "turns": 0, "text": ""}
    async for m in query(prompt=stream(), options=opt):
        if isinstance(m, AssistantMessage):
            for b in m.content:
                if isinstance(b, ToolUseBlock):
                    print(f"  [{label}] {b.name} {str(b.input.get('file_path') or b.input.get('pattern') or '')[:100]}",
                          flush=True)
                elif isinstance(b, TextBlock):
                    text.append(b.text)
        elif isinstance(m, ResultMessage):
            out.update(cost_usd=m.total_cost_usd or 0.0, subtype=m.subtype, turns=m.num_turns)
    out["text"] = "\n".join(text)
    return out


def parse_critic(text: str) -> dict | None:
    """Take the last JSON object in the critic's answer, cap each score, recompute the total."""
    decoder, found = json.JSONDecoder(), []
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text, i)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and all(k in obj for k in CRITIC_MAX):
            found.append(obj)
    for data in reversed(found):
        try:
            [int(data[k]) for k in CRITIC_MAX]
        except (TypeError, ValueError):
            continue
        scores = {k: max(0, min(int(data[k]), mx)) for k, mx in CRITIC_MAX.items()}
        scores["total"] = sum(scores.values())
        scores["notes"] = data.get("notes") or []
        return scores
    return None


# ---------------------------------------------------------------- analyze
def analyze(cfg, client: dfsmod.DFS, cache_only: bool, keywords: list) -> tuple[dict, list]:
    data, notes = {"volume": {}, "serp": {}, "ranked": None}, []
    if not keywords:
        return data, ["no target keywords in config"]
    try:
        data["volume"] = dfsmod.volumes(client.search_volume(keywords, cache_only=cache_only))
    except (dfsmod.DFSError, dfsmod.CapReached) as e:
        notes.append(f"search volume: {e}")
    for kw in keywords:
        try:
            data["serp"][kw] = dfsmod.serp_top(client.serp(kw, cache_only=cache_only))
        except (dfsmod.DFSError, dfsmod.CapReached) as e:
            notes.append(f"serp {kw}: {e}")
    domain = urlparse(cfg["site_url"]).netloc or cfg["site_url"]
    if cfg.get("track_domain", True):
        try:
            data["ranked"] = dfsmod.ranked(client.ranked_keywords(domain, cache_only=cache_only))
        except (dfsmod.DFSError, dfsmod.CapReached) as e:
            notes.append(f"ranked keywords {domain}: {e}")
    return data, notes


def gsc_opportunities(cfg, today: dt.date, pages: list, cache_dir: Path, dry_run: bool) -> tuple[dict | None, str]:
    """Step 02, second source: the site's own searches from Search Console (free).
    Last 28 days by page+query, the 28 days before by page. Cached for a day."""
    from seoloop import opportunities as op
    import verify
    end = today - dt.timedelta(days=verify.GSC_LAG_DAYS)
    start, prev_end = end - dt.timedelta(days=27), end - dt.timedelta(days=28)
    prev_start = prev_end - dt.timedelta(days=27)
    cache = cache_dir / f"gsc-{end.isoformat()}.json"
    if cache.exists():
        raw = json.loads(cache.read_text(encoding="utf-8"))
    else:
        key_env = cfg["verify"].get("gsc_key_env") or "GSC_KEY_FILE"
        if dry_run or not os.environ.get(key_env):
            return None, f"Search Console opportunities skipped ({'dry run' if dry_run else key_env + ' not set'})"
        client = verify.GSC(os.environ[key_env], cfg["verify"].get("gsc_property") or cfg["site_url"])
        raw = {"now": client.query(start, end, ["page", "query"]), "prev": client.query(prev_start, prev_end, ["page"])}
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(raw), encoding="utf-8")
    found = op.find(raw["now"], raw["prev"], pages, cfg.get("find") or {})
    found["_window"] = (start.isoformat(), end.isoformat())
    n = sum(len(v) for k, v in found.items() if not k.startswith("_"))
    return found, f"Search Console: {n} opportunities ({', '.join(f'{len(v)} {k}' for k, v in found.items() if not k.startswith('_'))})"


def data_markdown(cfg, data: dict, notes: list, today: dt.date) -> str:
    loc, lang = cfg["location_code"], cfg["language_code"]
    out = [f"# Search data, {today.isoformat()}", "",
           f"Source: DataForSEO, Google, location_code {loc}, language_code {lang}, desktop, measured {today}.", ""]
    out += ["## Search volume (Google Ads, monthly average)", "", "| Keyword | Volume | Competition | CPC |",
            "| --- | --- | --- | --- |"]
    for kw in cfg["target_keywords"]:
        v = data["volume"].get(kw) or next((x for k, x in data["volume"].items() if norm(k) == norm(kw)), None)
        if not v:
            out.append(f"| {kw} | not returned | | |")
        elif v["volume"] is None:
            out.append(f"| {kw} | null (Google Ads has no figure; not zero) | | |")
        else:
            out.append(f"| {kw} | {v['volume']} | {v['competition'] or ''} | {v['cpc'] if v['cpc'] is not None else ''} |")
    for kw, s in data["serp"].items():
        out += ["", f"## Top 10: {kw}", "", f"SERP features: {', '.join(s['features']) or 'none'}", ""]
        if s["empty"]:
            out.append("Empty result. Recorded as data, not replaced.")
        out += [f"{o['pos']}. {o['domain']}: {o['title']} ({o['url']})" for o in s["organic"]]
    out += ["", f"## Ranked keywords for {urlparse(cfg['site_url']).netloc}", ""]
    if data["ranked"] is None:
        out.append("Not measured this run.")
    elif not data["ranked"]:
        out.append("None. The domain ranks for no keyword in this market (empty result).")
    else:
        out += [f"- {r['keyword']}: position {r['pos']} ({r['url']})" for r in data["ranked"][:100]]
    if data.get("gsc"):
        from seoloop import opportunities as op
        g = {k: v for k, v in data["gsc"].items() if not k.startswith("_")}
        out += ["", op.markdown(g, *data["gsc"]["_window"])]
    if notes:
        out += ["", "## Gaps", ""] + [f"- {n}" for n in notes]
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- helpers
def snapshot(content_dir: Path, ext: str) -> dict:
    return {p.resolve(): p.read_text(encoding="utf-8") for p in content_dir.rglob(f"*{ext}")} if content_dir.exists() else {}


def fill(template: str, **values) -> str:
    for k, v in values.items():
        template = template.replace("{{" + k + "}}", str(v))
    return template


def existing_pages(content_dir: Path, ext: str) -> list:
    rows = []
    for p in sorted(content_dir.rglob(f"*{ext}")) if content_dir.exists() else []:
        fm, _ = gate.parse_page(p.read_text(encoding="utf-8"))
        rows.append((p, fm.get("title", ""), fm.get("keyword", "")))
    return rows


def rel(p: Path, root: Path) -> str:
    try:
        return str(Path(p).resolve().relative_to(root))
    except ValueError:
        return str(p)


def park(page: Path, before: str | None, run_dir: Path) -> None:
    """Take a failed page out of the content dir: restore the old text or move the new file aside."""
    if before is not None:
        page.write_text(before, encoding="utf-8")
        return
    dest = run_dir / "rejected" / page.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(page), dest)


# ---------------------------------------------------------------- main
def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--dry-run", action="store_true", help="no model calls, no paid calls; print the plan")
    ap.add_argument("--budget", type=float, help="max USD for this run (model + data); default from config")
    ap.add_argument("--model", help="builder model; default from config")
    ap.add_argument("--critic-model", help="critic model; default from config")
    ap.add_argument("--advisor", help="advisor model passed to Claude Code, e.g. claude-fable-5-1")
    ap.add_argument("--max-pages", type=int, help="pages to build this run; default from config")
    ap.add_argument("--draft-only", action="store_true", help="keep passing tasks open instead of marking them shipped")
    ap.add_argument("--dfs-command", help="same as DATAFORSEO_COMMAND: an existing helper that takes "
                                          "<endpoint> '<json>' and prints the raw response")
    ap.add_argument("--today", help="YYYY-MM-DD, for tests")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    a = parse_args(argv)
    cfg = load_config(a.config)
    today = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
    b = cfg["budget"]
    budget = RunBudget(max_usd=float(a.budget if a.budget is not None else b["max_usd_per_run"]),
                       max_tasks=int(b["max_tasks_per_run"]))
    max_pages = min(int(a.max_pages if a.max_pages is not None else b["max_pages_per_run"]), budget.max_tasks)
    builder_model = a.model or cfg["models"]["builder"]
    critic_model = a.critic_model or cfg["models"]["critic"]
    advisor = a.advisor or cfg["models"].get("advisor") or ""
    pass_score = int(cfg["critic"]["pass_score"])
    root, content_dir, loop_dir = cfg["_root"], cfg["_content_dir"], cfg["_loop_dir"]
    ext = cfg["page_extension"]
    run_id = f"{today.isoformat()}-seo"
    run_dir = loop_dir / "runs" / run_id
    n = 2
    while run_dir.exists() and not a.dry_run:
        run_dir = loop_dir / "runs" / f"{run_id}-{n}"
        n += 1
    board_path = loop_dir / "board.md"
    board = Board.load(board_path)
    started = time.time()

    print(f"seo-loop: {cfg['site_url']} | {today} | budget ${budget.max_usd:.2f}, {budget.max_tasks} tasks, "
          f"{max_pages} page(s) | builder {builder_model}, critic {critic_model}"
          + (f", advisor {advisor}" if advisor else ""))

    # 01 check the board
    due = board.mark_due(today)
    print(f"01 board: {len(board.in_section('open'))} open, {len(board.in_section('shipped'))} shipped, "
          f"{len(board.in_section('due'))} due for verify, {len(board.in_section('rejected'))} rejected")
    verify_note = "nothing due"
    if board.in_section("due"):
        key_env = cfg["verify"].get("gsc_key_env") or "GSC_KEY_FILE"
        if a.dry_run:
            verify_note = f"{len(board.in_section('due'))} due; dry run, not checked"
        elif not os.environ.get(key_env):
            verify_note = f"{len(board.in_section('due'))} due; {key_env} not set, skipped"
        else:
            import verify
            board.save(board_path)
            report = verify.run(cfg, today, apply=True)
            board = Board.load(board_path)
            verify_note = "; ".join(f"{r['id']}: {r['verdict']} ({r['reason']})" for r in report)
    print(f"08 verify: {verify_note}")

    # 02 analyze
    if a.dfs_command:
        os.environ["DATAFORSEO_COMMAND"] = a.dfs_command
    have_creds = bool(os.environ.get("DATAFORSEO_COMMAND") or (
        (os.environ.get("DATAFORSEO_LOGIN") or os.environ.get("DATAFORSEO_USERNAME"))
        and os.environ.get("DATAFORSEO_PASSWORD")))
    cache_only = a.dry_run or not have_creds
    dfs_cap = min(float(b["dataforseo_cap_usd"]), budget.max_usd)
    client = dfsmod.DFS(loop_dir / "cache" / "dfs", dfs_cap, cfg["location_code"], cfg["language_code"],
                        log_path=None if a.dry_run else loop_dir / "dfs-log.md")
    keywords = [k for k in cfg["target_keywords"] if norm(k) not in board.keywords(("shipped", "due", "rejected"))]
    data, notes = analyze(cfg, client, cache_only, keywords)
    budget.charge("dataforseo", client.spent_usd)
    hits = sum(1 for c in client.calls if c["cache"])
    print(f"02 analyze: {len(keywords)} keywords, {len(client.calls)} calls answered ({hits} from cache), "
          f"DataForSEO ${client.spent_usd:.4f} of ${dfs_cap:.2f} cap"
          + ("" if have_creds or a.dry_run else " | no DataForSEO credentials: cache only"))
    for note in notes:
        print(f"   gap: {note}")
    data["gsc"], gsc_note = gsc_opportunities(cfg, today, existing_pages(content_dir, ext), loop_dir / "cache" / "gsc", a.dry_run)
    print(f"02 analyze: {gsc_note}")

    guard_kw = dict(read_roots=[root, loop_dir], write_roots=[content_dir, run_dir])
    if a.dry_run:
        print("\nDry run. Nothing was written, no model was called. Next steps would be:")
        print(f"  03-05 builder query ({builder_model}): tools Read/Glob/Grep/Write/Edit, "
              f"writes only {rel(content_dir, root)}/ and {rel(run_dir, root)}/")
        print(f"  04 gate: build ({cfg['build_command'] or 'skipped, no build_command'}), title <= 60, "
              f"description <= 155, no new noindex, keyword in title/H1/first paragraph, no duplicate")
        print(f"  06 critic query ({critic_model}): tools Read/Glob/Grep, pass >= {pass_score}/20, one rewrite")
        print(f"  07 ship: print git commands for branch seo-loop/{today}; nothing is pushed")
        print(f"  existing pages: {len(existing_pages(content_dir, ext))}, budget ${budget.max_usd:.2f}")
        return 0

    run_dir.mkdir(parents=True, exist_ok=True)
    content_dir.mkdir(parents=True, exist_ok=True)
    data_path = run_dir / "data.md"
    data_path.write_text(data_markdown(cfg, data, notes, today), encoding="utf-8")
    tasks_path = run_dir / "tasks.json"
    log = {"run": run_dir.name, "date": today.isoformat(), "site": cfg["site_url"], "queries": [],
           "pages": [], "verify": verify_note, "dfs_calls": client.calls, "notes": notes}

    # 03-05 tasks + build
    before = snapshot(content_dir, ext)
    pages_list = "\n".join(f"- {rel(p, root)}: {t} (keyword: {k or '-'})"
                           for p, t, k in existing_pages(content_dir, ext)) or "- none yet"
    copy_rules = (f"read `{cfg['copy_rules']}` (relative to {root})" if cfg["copy_rules"]
                  else "plain, specific, no hype words, no em dashes, short sentences.")
    prompt = fill((KIT / "prompts" / "build.md").read_text(encoding="utf-8"),
                  site_url=cfg["site_url"], language=cfg["language"], today=today, data_path=data_path,
                  location_code=cfg["location_code"], language_code=cfg["language_code"],
                  content_dir=content_dir, content_dir_rel=rel(content_dir, root), copy_rules=copy_rules,
                  max_tasks=budget.max_tasks, tasks_path=tasks_path, page_ext=ext, max_pages=max_pages,
                  run_dir=run_dir, board=board.render()) + f"\n\n## Existing pages\n\n{pages_list}\n"
    stop = budget.stop_reason()
    if not stop:
        res = asyncio.run(ask(prompt, model=builder_model, label="build", cwd=root, advisor=advisor,
                              budget_usd=budget.remaining_usd - CRITIC_RESERVE_USD * max_pages,
                              tools=["Read", "Glob", "Grep", "Write", "Edit"], guard=make_guard(**guard_kw)))
        budget.charge("builder", res["cost_usd"])
        log["queries"].append({"step": "build", "model": builder_model, "cost_usd": res["cost_usd"],
                               "result": res["subtype"], "turns": res["turns"]})
        log["builder_summary"] = res["text"][-1500:]
        print(f"05 build: {res['subtype']}, ${res['cost_usd']:.2f}")

    tasks = []
    if tasks_path.exists():
        try:
            tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            notes.append("tasks.json was not valid JSON")
    created = []
    for t in tasks[: budget.max_tasks]:
        if not isinstance(t, dict) or not t.get("keyword"):
            continue
        task = board.add(t.get("type", "new-page"), today, keyword=t["keyword"], target=t.get("target", ""),
                         why=t.get("why", ""), hypothesis=t.get("hypothesis", ""),
                         verify_metric=t.get("verify_metric", ""))
        if task:
            created.append((task, t))
    print(f"03 tasks: {len(created)} new on the board ({len(tasks)} proposed)")

    after = snapshot(content_dir, ext)
    changed = [p for p in after if before.get(p) != after[p]]
    by_kw = {norm(task.get("keyword")): task for task, _ in created}
    by_kw.update({norm(t.get("keyword")): t for t in board.in_section("open") if t.get("keyword")})

    shipped_pages = []
    for page in changed[:max_pages]:
        fm, _ = gate.parse_page(page.read_text(encoding="utf-8"))
        task = by_kw.get(norm(fm.get("keyword", "")))
        entry = {"page": rel(page, root), "task": task.id if task else None, "gate": [], "critic": []}
        log["pages"].append(entry)
        passed = False
        for attempt in range(1 + int(cfg["critic"]["max_rewrites"])):
            checks = [gate.run_build(cfg["build_command"], root)] + gate.check_page(page, content_dir, before.get(page), ext)
            entry["gate"].append([c.line() for c in checks])
            print(f"04 gate {rel(page, root)} (attempt {attempt + 1}): "
                  f"{'pass' if gate.passed(checks) else 'FAIL'}")
            fix = [c.line() for c in checks if not c.ok]
            if not fix:
                if not budget.can_afford(0.05):
                    notes.append(f"budget stop before critic of {page.name}")
                    break
                cprompt = (f"Grade this page: {page}\nSearch data: {data_path}\nSite: {cfg['site_url']}, "
                           f"language {cfg['language']}.\nCopy rules: {copy_rules}\nExisting pages are in "
                           f"{content_dir}. Follow the rubric in your instructions and end with the JSON block.")
                cres = asyncio.run(ask(cprompt, model=critic_model, label="critic", cwd=root, advisor=advisor,
                                       system=(KIT / "critic.md").read_text(encoding="utf-8"),
                                       budget_usd=min(budget.remaining_usd, 2.0), tools=["Read", "Glob", "Grep"],
                                       guard=make_guard(read_roots=[content_dir, run_dir, root], write_roots=[])))
                budget.charge("critic", cres["cost_usd"])
                log["queries"].append({"step": "critic", "model": critic_model, "cost_usd": cres["cost_usd"],
                                       "result": cres["subtype"], "turns": cres["turns"]})
                score = parse_critic(cres["text"])
                (run_dir / f"critic-{page.stem}-{attempt + 1}.md").write_text(cres["text"], encoding="utf-8")
                entry["critic"].append(score or {"total": None, "notes": ["critic gave no parsable score"]})
                total = score["total"] if score else 0
                print(f"06 critic {page.name}: {total}/20 (${cres['cost_usd']:.2f})")
                if total >= pass_score:
                    passed = True
                    break
                fix = (score or {}).get("notes") or ["critic gave no parsable score; tighten facts and intent"]
            if attempt >= int(cfg["critic"]["max_rewrites"]) or budget.stop_reason():
                break
            rprompt = (f"Rewrite {page} once. Fix exactly these findings and nothing else:\n- " + "\n- ".join(map(str, fix))
                       + f"\nKeep the frontmatter format. Search data: {data_path}. Only edit that file.")
            rres = asyncio.run(ask(rprompt, model=builder_model, label="rewrite", cwd=root, advisor=advisor,
                                   budget_usd=max(0.05, budget.remaining_usd - CRITIC_RESERVE_USD),
                                   tools=["Read", "Glob", "Grep", "Edit", "Write"],
                                   guard=make_guard(read_roots=[root, loop_dir], write_roots=[page])))
            budget.charge("rewrite", rres["cost_usd"])
            log["queries"].append({"step": "rewrite", "model": builder_model, "cost_usd": rres["cost_usd"],
                                   "result": rres["subtype"], "turns": rres["turns"]})
        last_score = entry["critic"][-1]["total"] if entry["critic"] else None
        if task:
            task.fields.update(page=rel(page, root), critic=f"{last_score}/20" if last_score is not None else "none")
        if passed:
            shipped_pages.append(page)
            if task and not a.draft_only:
                board.move(task, "shipped", shipped=today.isoformat(),
                           verify=(today + dt.timedelta(days=int(cfg["verify"]["after_days"]))).isoformat(),
                           pr=f"seo-loop/{today}")
            elif task:
                task.fields["draft"] = "passed gate and critic"
        else:
            gate_fails = [line for line in (entry["gate"][-1] if entry["gate"] else []) if line.startswith("FAIL")]
            park(page, before.get(page), run_dir)
            if gate_fails or entry["critic"]:
                reason = ("gate: " + "; ".join(gate_fails)) if gate_fails else \
                         f"critic {last_score}/20 after {len(entry['critic'])} grading(s)"
                if task:
                    board.move(task, "rejected", rejected=today.isoformat(), reason=reason)
            elif task:  # budget stop before grading: the task stays open for the next run
                task.fields["note"] = "budget stop before critic; page moved to run folder"
        budget.task_finished()
        if budget.stop_reason():
            notes.append(f"stop rule: {budget.stop_reason()}")
            break
    for page in changed[max_pages:]:
        park(page, before.get(page), run_dir)
        notes.append(f"{page.name}: over the page limit, moved aside")

    board.save(board_path)

    # 07 ship: write the PR text, print commands, never run them
    branch = f"seo-loop/{today}"
    log.update(cost=budget.ledger, total_usd=round(budget.spent_usd, 4), minutes=round((time.time() - started) / 60, 1),
               stop=budget.stop_reason(), ship=bool(shipped_pages) and not a.draft_only, branch=branch,
               notes=notes, tasks_created=[t.id for t, _ in created])
    (run_dir / "result.json").write_text(json.dumps(log, indent=1, default=str), encoding="utf-8")
    write_log(run_dir / "log.md", cfg, log, data_path, board_path, root)
    with (loop_dir / "runs.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"run": run_dir.name, "total_usd": log["total_usd"], "ship": log["ship"],
                            "pages": len(shipped_pages), "minutes": log["minutes"]}) + "\n")
    print(f"\nRun log: {rel(run_dir / 'log.md', root)} | total ${budget.spent_usd:.2f}")
    if shipped_pages and not a.draft_only:
        files = " ".join(rel(p, root) for p in shipped_pages)
        (run_dir / "pr.md").write_text(pr_body(log, root), encoding="utf-8")
        print("\n07 ship. Nothing was pushed. To open the PR yourself:\n"
              f"  git switch -c {branch}\n"
              f"  git add {files} {rel(board_path, root)} {rel(run_dir, root)}\n"
              f"  git commit -m \"seo-loop: {len(shipped_pages)} page(s), gate and critic passed\"\n"
              f"  git push -u origin {branch}\n"
              f"  gh pr create --title \"SEO loop {today}\" --body-file {rel(run_dir / 'pr.md', root)}")
    elif not shipped_pages:
        print("07 ship: nothing passed gate and critic. Nothing to ship.")
    return 0


def pr_body(log: dict, root: Path) -> str:
    lines = [f"SEO loop run {log['run']}. Gate and critic passed for:", ""]
    for p in log["pages"]:
        if p["critic"] and (p["critic"][-1].get("total") or 0):
            lines.append(f"- `{p['page']}` ({p['task']}): critic {p['critic'][-1]['total']}/20")
    lines += ["", f"Run cost: ${log['total_usd']:.2f}. Verify date: 21 days after merge.",
              "Search data and the critic notes are in the run folder. A human merges."]
    return "\n".join(lines) + "\n"


def write_log(path: Path, cfg: dict, log: dict, data_path: Path, board_path: Path, root: Path) -> None:
    dfs_total = sum(c.get("cost_usd", 0) for c in log["dfs_calls"])
    model_total = sum(q["cost_usd"] or 0 for q in log["queries"])
    out = [f"# SEO loop run {log['run']}", "",
           f"Site {cfg['site_url']}, market location_code {cfg['location_code']} / language_code "
           f"{cfg['language_code']}.", "",
           "## 1. What was measured", "",
           f"DataForSEO, {len(log['dfs_calls'])} calls ({sum(1 for c in log['dfs_calls'] if c.get('cache'))} from cache). "
           f"Data with parameters: `{rel(data_path, root)}`.", ""]
    out += [f"- {c['label']}: ${c.get('cost_usd', 0):.4f}{' (cache)' if c.get('cache') else ''}" for c in log["dfs_calls"]]
    out += ["", f"Verify (step 08): {log['verify']}", "", "## 2. What changed since the last run", "",
            f"Tasks added: {', '.join(log['tasks_created']) or 'none'}. Board: `{rel(board_path, root)}`.", "",
            "## 3. What was changed, file by file", ""]
    if not log["pages"]:
        out.append("Nothing. A run without a finding is a valid run.")
    for p in log["pages"]:
        score = p["critic"][-1]["total"] if p["critic"] else None
        out += [f"### `{p['page']}` ({p['task'] or 'no task'})", "",
                "Gate, last attempt:", ""] + [f"- {line}" for line in (p["gate"][-1] if p["gate"] else [])]
        out += ["", f"Critic: {score if score is not None else 'not run'}/20 "
                    f"({len(p['critic'])} grading(s))", ""]
        if p["critic"] and p["critic"][-1].get("notes"):
            out += [f"- {n}" for n in p["critic"][-1]["notes"]] + [""]
    out += ["## 4. Proposed, not changed", "", log.get("builder_summary", "").strip() or "Nothing.", "",
            "## 5. What it cost", "", "| Step | Model | Result | USD |", "| --- | --- | --- | --- |"]
    out += [f"| {q['step']} | {q['model']} | {q['result']} | {q['cost_usd']:.4f} |" for q in log["queries"]]
    out += [f"| DataForSEO | | | {dfs_total:.4f} |", f"| **Total** | | | **{model_total + dfs_total:.4f}** |", "",
            f"Stop rule: {log['stop'] or 'not reached'}. Duration {log['minutes']} min."]
    if log["notes"]:
        out += ["", "## Notes", ""] + [f"- {n}" for n in log["notes"]]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
