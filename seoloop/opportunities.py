"""Search Console opportunities for step 02 (free data, the site's own searches).

Input: Search Console rows for the last 28 days by (page, query), and by page for the
28 days before. Output: four kinds of findings the builder can turn into tasks:

  striking   a query where a page ranks 8-20 with real impressions     -> task type improve
  snippet    top-10 query with many impressions but a weak click rate   -> task type snippet
  gap        a query with impressions but no page that fits it          -> task type new-page
  decay      a page with clearly fewer clicks than the 28 days before   -> task type refresh

Thresholds come from `verify.find` in the config (defaults below). Pure functions, no network.
"""
from __future__ import annotations

import re

DEFAULTS = {
    "min_impressions": 50,      # striking distance and gaps need at least this many
    "striking_from": 8.0,       # average position range for "almost on page 1"
    "striking_to": 20.0,
    "snippet_impressions": 100,
    "snippet_max_ctr": 0.01,    # under 1 % in the top 10 = the snippet does not sell the click
    "gap_min_position": 20.0,   # best page ranks below this = no page really answers the query
    "decay_drop": 0.3,          # 30 % fewer clicks than the 28 days before
    "decay_min_clicks": 20,     # only pages that had real traffic before
    "max_each": 10,
}


def words(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) > 2}


def covers(query: str, pages: list) -> str | None:
    """A page 'fits' a query when its keyword, title or slug carries most of the query's words."""
    q = words(query)
    if not q:
        return None
    for path, title, keyword in pages:
        have = words(keyword) | words(title) | words(str(path))
        if len(q & have) / len(q) >= 0.75:
            return str(path)
    return None


def find(now_rows: list, prev_rows: list, pages: list, cfg: dict | None = None) -> dict:
    """now_rows: [{"keys": [page, query], clicks, impressions, ctr, position}],
    prev_rows: [{"keys": [page], clicks, ...}], pages: [(path, title, keyword)] of the content dir."""
    c = {**DEFAULTS, **(cfg or {})}
    out = {"striking": [], "snippet": [], "gap": [], "decay": []}

    best = {}  # per query: the best-ranking page
    for r in now_rows:
        page, query = r["keys"][0], r["keys"][1]
        row = {"page": page, "query": query, "clicks": r.get("clicks", 0), "impressions": r.get("impressions", 0),
               "ctr": r.get("ctr", 0.0), "position": r.get("position", 99.0)}
        if query not in best or row["position"] < best[query]["position"]:
            best[query] = {**row, "total_impressions": best.get(query, {}).get("total_impressions", 0)}
        best[query]["total_impressions"] = best[query].get("total_impressions", 0) + row["impressions"]

    for q, b in best.items():
        imp, pos = b["total_impressions"], b["position"]
        fits = covers(q, pages)
        if imp >= c["min_impressions"] and (pos > c["gap_min_position"] or fits is None):
            out["gap"].append({**b, "task": "new-page", "fits": fits})
        elif c["striking_from"] <= pos <= c["striking_to"] and imp >= c["min_impressions"]:
            out["striking"].append({**b, "task": "improve", "fits": fits})
        elif pos < c["striking_from"] and imp >= c["snippet_impressions"] and b["ctr"] < c["snippet_max_ctr"]:
            out["snippet"].append({**b, "task": "snippet", "fits": fits})

    now_pages = {}
    for r in now_rows:
        now_pages[r["keys"][0]] = now_pages.get(r["keys"][0], 0) + r.get("clicks", 0)
    for r in prev_rows:
        page, before = r["keys"][0], r.get("clicks", 0)
        after = now_pages.get(page, 0)
        if before >= c["decay_min_clicks"] and after <= before * (1 - c["decay_drop"]):
            out["decay"].append({"page": page, "clicks_before": before, "clicks_now": after,
                                 "drop": round(1 - after / before, 2), "task": "refresh"})

    out["striking"].sort(key=lambda x: -x["total_impressions"])
    out["snippet"].sort(key=lambda x: -x["total_impressions"])
    out["gap"].sort(key=lambda x: -x["total_impressions"])
    out["decay"].sort(key=lambda x: -(x["clicks_before"] - x["clicks_now"]))
    return {k: v[: c["max_each"]] for k, v in out.items()}


def markdown(op: dict, start, end) -> str:
    """The section for data.md that the builder reads."""
    out = [f"## Search Console opportunities ({start} to {end}, the site's own searches)", ""]
    if not any(op.values()):
        return "\n".join(out + ["No opportunity above the thresholds. Recorded as data.", ""])
    if op["striking"]:
        out += ["### Almost on page 1 (position 8-20): task type `improve`", "", "| Query | Page | Position | Impressions | Clicks |", "| --- | --- | --- | --- | --- |"]
        out += [f"| {x['query']} | {x['page']} | {x['position']:.1f} | {x['total_impressions']} | {x['clicks']} |" for x in op["striking"]]
        out.append("")
    if op["snippet"]:
        out += ["### Seen but not clicked (top 10, CTR under 1 %): task type `snippet`", "", "| Query | Page | Position | Impressions | CTR |", "| --- | --- | --- | --- | --- |"]
        out += [f"| {x['query']} | {x['page']} | {x['position']:.1f} | {x['total_impressions']} | {x['ctr'] * 100:.2f} % |" for x in op["snippet"]]
        out.append("")
    if op["gap"]:
        out += ["### Content gaps (searched, no page fits): task type `new-page`", "", "| Query | Best page now | Position | Impressions |", "| --- | --- | --- | --- |"]
        out += [f"| {x['query']} | {x['page']} | {x['position']:.1f} | {x['total_impressions']} |" for x in op["gap"]]
        out.append("")
    if op["decay"]:
        out += ["### Losing clicks (vs the 28 days before): task type `refresh`", "", "| Page | Clicks before | Clicks now | Drop |", "| --- | --- | --- | --- |"]
        out += [f"| {x['page']} | {x['clicks_before']} | {x['clicks_now']} | {x['drop'] * 100:.0f} % |" for x in op["decay"]]
        out.append("")
    return "\n".join(out)
