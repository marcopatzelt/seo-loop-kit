#!/usr/bin/env python3
"""Step 08: the 21-day check against Google Search Console.

For every task in "Due for verify" (and shipped tasks whose verify date has
come), read clicks, impressions, CTR and position for the page over the 21
days after it shipped, then decide:

  ranked, nobody clicked   position <= 10, impressions >= 100, CTR < 0.5 %  -> reopen (type: snippet)
  invisible                impressions < 50 and position > 30 (or no rows) -> reopen (type: improve)
  working                  clicks > 0 or position <= 10                    -> verified
  otherwise                                                               -> reopen (type: improve)

Access: a Google service account JSON key, path in the environment variable
named by `verify.gsc_key_env` (default GSC_KEY_FILE). Scope is read-only:
https://www.googleapis.com/auth/webmasters.readonly. Add the service
account to the Search Console property with "Restricted" permission.

  python verify.py --config loops/seo-loop/config.yaml            # report only
  python verify.py --config loops/seo-loop/config.yaml --apply    # also update board.md
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from seoloop.board import Board  # noqa: E402
from seoloop.config import load_config  # noqa: E402

SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
GSC_LAG_DAYS = 3  # Search Console data arrives about three days late

POS_TOP = 10
MIN_IMPRESSIONS = 100
MIN_CTR = 0.005


def judge(row: dict | None) -> tuple[str, str, str]:
    """Return (verdict, reopen_type, reason). verdict is 'verified' or 'reopen'."""
    if not row or not row.get("impressions"):
        return "reopen", "improve", "no impressions in the window"
    clicks = row.get("clicks", 0)
    impressions = row.get("impressions", 0)
    ctr = row.get("ctr", clicks / impressions if impressions else 0.0)
    pos = row.get("position", 999.0)
    if pos <= POS_TOP and impressions >= MIN_IMPRESSIONS and ctr < MIN_CTR:
        return "reopen", "snippet", (f"ranked but no clicks: position {pos:.1f}, {impressions} impressions, "
                                     f"CTR {ctr * 100:.2f} %")
    if impressions < 50 and pos > 30:
        return "reopen", "improve", f"invisible: position {pos:.1f}, {impressions} impressions"
    if clicks > 0 or pos <= POS_TOP:
        return "verified", "", f"{clicks} clicks, position {pos:.1f}, {impressions} impressions"
    return "reopen", "improve", f"no clicks, position {pos:.1f}, {impressions} impressions"


def window(shipped: dt.date, today: dt.date, days: int = 21) -> tuple[dt.date, dt.date]:
    end = min(shipped + dt.timedelta(days=days), today - dt.timedelta(days=GSC_LAG_DAYS))
    return shipped + dt.timedelta(days=1), end


class GSC:
    """Read-only Search Console client. Only searchAnalytics.query is used."""

    def __init__(self, key_file: str, site_property: str):
        from google.oauth2 import service_account
        from google.auth.transport.requests import AuthorizedSession
        creds = service_account.Credentials.from_service_account_file(key_file, scopes=[SCOPE])
        self.session = AuthorizedSession(creds)
        self.site = site_property

    def query(self, start: dt.date, end: dt.date, dimensions: list, row_limit: int = 5000) -> list:
        """searchAnalytics.query over the whole property, e.g. dimensions ["page", "query"] (step 02)."""
        url = ("https://www.googleapis.com/webmasters/v3/sites/"
               f"{urllib.parse.quote(self.site, safe='')}/searchAnalytics/query")
        body = {"startDate": start.isoformat(), "endDate": end.isoformat(), "dimensions": dimensions,
                "type": "web", "rowLimit": row_limit}
        r = self.session.post(url, json=body, timeout=60)
        if r.status_code != 200:
            raise RuntimeError(f"Search Console HTTP {r.status_code}")
        return r.json().get("rows") or []

    def page_rows(self, start: dt.date, end: dt.date, page_url: str) -> dict | None:
        url = ("https://www.googleapis.com/webmasters/v3/sites/"
               f"{urllib.parse.quote(self.site, safe='')}/searchAnalytics/query")
        body = {"startDate": start.isoformat(), "endDate": end.isoformat(), "dimensions": ["page"],
                "type": "web", "rowLimit": 10,
                "dimensionFilterGroups": [{"filters": [{"dimension": "page", "operator": "equals",
                                                        "expression": page_url}]}]}
        r = self.session.post(url, json=body, timeout=60)
        if r.status_code != 200:
            raise RuntimeError(f"Search Console HTTP {r.status_code}")
        rows = r.json().get("rows") or []
        return rows[0] if rows else None


def page_url(site_url: str, target: str) -> str:
    if target.startswith("http"):
        return target
    return site_url.rstrip("/") + "/" + target.lstrip("/")


def run(cfg: dict, today: dt.date, apply: bool = False, client=None) -> list[dict]:
    board_path = cfg["_loop_dir"] / "board.md"
    board = Board.load(board_path)
    board.mark_due(today)
    due = board.in_section("due")
    if not due:
        return []
    if client is None:
        key_env = cfg["verify"].get("gsc_key_env") or "GSC_KEY_FILE"
        key_file = os.environ.get(key_env)
        prop = cfg["verify"].get("gsc_property") or cfg["site_url"]
        if not key_file:
            raise RuntimeError(f"{key_env} is not set; cannot read Search Console")
        client = GSC(key_file, prop)
    days = int(cfg["verify"].get("after_days", 21))
    report = []
    for t in due:
        shipped = t.date("shipped") or today - dt.timedelta(days=days)
        start, end = window(shipped, today, days)
        url = page_url(cfg["site_url"], t.get("target"))
        row = client.page_rows(start, end, url) if end >= start else None
        verdict, reopen_type, reason = judge(row)
        report.append({"id": t.id, "url": url, "window": f"{start}..{end}", "row": row,
                       "verdict": verdict, "reason": reason})
        if apply:
            if verdict == "verified":
                board.move(t, "shipped", verified=today.isoformat(), result=reason)
            else:
                board.move(t, "open", type_was=t.type, reopened=today.isoformat(), why=reason)
                t.type = reopen_type
    if apply:
        board.save(board_path)
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--apply", action="store_true", help="write verdicts into board.md")
    ap.add_argument("--today", help="YYYY-MM-DD, for testing")
    a = ap.parse_args()
    cfg = load_config(a.config)
    today = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
    try:
        report = run(cfg, today, a.apply)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=1, default=str) if report else "Nothing due for verify.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
