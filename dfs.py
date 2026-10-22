#!/usr/bin/env python3
"""Small DataForSEO client with a per-run cost cap and a cache folder.

Four calls, all live endpoints:
  search_volume(keywords)   /keywords_data/google_ads/search_volume/live
  keyword_ideas(seed)       /dataforseo_labs/google/keyword_ideas/live
  serp(keyword)             /serp/google/organic/live/advanced  (top 10)
  ranked_keywords(domain)   /dataforseo_labs/google/ranked_keywords/live

Credentials come from the environment only: DATAFORSEO_LOGIN (or
DATAFORSEO_USERNAME) and DATAFORSEO_PASSWORD. They are never printed.

Rules carried over from the original loop:
- One market per query: location_code and language_code are always sent.
  Never fall back to another country when a market has no data.
- No automatic retries and no redirects: retrying a paid call can bill twice.
- Every response is cached by request hash. A warm cache costs nothing.
- The cost is read from the response, not estimated from the balance.
- An empty result is a result. It is cached and reported, not replaced.

CLI:
  python dfs.py --check                                  free account check
  python dfs.py serp "grill me skill" --location 2840 --language en --cache .cache/dfs --cap 0.5
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.dataforseo.com/v3"

# Conservative upper estimates per call (USD), used only to refuse a call that
# would break the cap. The real cost is read from each response.
ESTIMATE = {
    "/keywords_data/google_ads/search_volume/live": 0.10,
    "/dataforseo_labs/google/keyword_ideas/live": 0.03,
    "/serp/google/organic/live/advanced": 0.004,
    "/dataforseo_labs/google/ranked_keywords/live": 0.03,
    "/appendix/user_data": 0.0,
}


class CapReached(RuntimeError):
    pass


class DFSError(RuntimeError):
    pass


def credentials(environ=None) -> tuple[str, str]:
    env = os.environ if environ is None else environ
    login = env.get("DATAFORSEO_LOGIN") or env.get("DATAFORSEO_USERNAME")
    password = env.get("DATAFORSEO_PASSWORD")
    if not login or not password:
        raise DFSError("DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD are not set")
    return login, password


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def command_transport(command: str):
    """Use an existing helper instead of credentials in this process.

    DATAFORSEO_COMMAND="python3 /path/to/helper.py" must accept `<endpoint> '<json body>'`
    and print the raw DataForSEO JSON response. The cap, cache and cost log still apply.
    """
    argv = shlex.split(command)

    def transport(path: str, body):
        if body is None:
            raise DFSError("GET is not supported through DATAFORSEO_COMMAND")
        proc = subprocess.run(argv + [path, json.dumps(body)], capture_output=True, text=True, timeout=300)
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError:
            raise DFSError(f"DATAFORSEO_COMMAND returned no JSON (exit {proc.returncode})") from None
    return transport


def succeeded(data: dict) -> bool:
    tasks = data.get("tasks") or []
    return (data.get("status_code") == 20000 and bool(tasks) and not data.get("tasks_error", 0)
            and all(t and t.get("status_code") == 20000 for t in tasks))


class DFS:
    def __init__(self, cache_dir: str | Path, cap_usd: float, location_code: int, language_code: str,
                 transport=None, log_path: str | Path | None = None):
        self.cache_dir = Path(cache_dir)
        self.cap_usd = float(cap_usd)
        self.location_code = int(location_code)
        self.language_code = language_code
        self.spent_usd = 0.0
        self.calls: list[dict] = []
        command = os.environ.get("DATAFORSEO_COMMAND", "")
        self._transport = transport or (command_transport(command) if command else self._http)
        self.log_path = Path(log_path) if log_path else None

    # ---- plumbing ------------------------------------------------------
    def _http(self, path: str, body):
        login, password = credentials()
        token = base64.b64encode(f"{login}:{password}".encode()).decode()
        req = urllib.request.Request(
            API + path, data=None if body is None else json.dumps(body).encode(),
            headers={"Authorization": "Basic " + token, "Content-Type": "application/json"},
            method="GET" if body is None else "POST")
        try:
            with urllib.request.build_opener(_NoRedirect()).open(req, timeout=300) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            raise DFSError(f"HTTP {e.code}; body hidden") from None
        except (urllib.error.URLError, TimeoutError):
            raise DFSError("connection failed or timed out; no retry") from None

    def cache_path(self, path: str, body) -> Path:
        """Readable and deterministic: <endpoint>-<subject>-<location>-<language>-<hash8>.json"""
        task = body[0] if isinstance(body, list) and body else {}
        subject = task.get("keyword") or task.get("target") or "_".join(task.get("keywords") or []) or "x"
        slug = re.sub(r"[^a-z0-9]+", "-", str(subject).lower()).strip("-")[:60] or "x"
        endpoint = {"/keywords_data/google_ads/search_volume/live": "volume",
                    "/dataforseo_labs/google/keyword_ideas/live": "ideas",
                    "/serp/google/organic/live/advanced": "serp",
                    "/dataforseo_labs/google/ranked_keywords/live": "ranked"}.get(
                        path, path.strip("/").replace("/", "_"))
        key = hashlib.sha256(json.dumps([path, body], sort_keys=True).encode()).hexdigest()[:8]
        return self.cache_dir / f"{endpoint}-{slug}-{task.get('location_code', '')}-{task.get('language_code', '')}-{key}.json"

    def cached(self, path: str, body) -> dict | None:
        p = self.cache_path(path, body)
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def call(self, path: str, body, label: str = "", cache_only: bool = False) -> dict:
        hit = self.cached(path, body)
        if hit is not None:
            self.calls.append({"label": label or path, "path": path, "cost_usd": 0.0, "cache": True})
            return hit
        if cache_only:
            raise CapReached(f"cache miss for {label or path} and network calls are off")
        estimate = ESTIMATE.get(path, 0.05)
        if self.spent_usd + estimate > self.cap_usd:
            raise CapReached(f"DataForSEO cap ${self.cap_usd:.2f} would be exceeded "
                             f"(spent ${self.spent_usd:.4f}, next call up to ${estimate:.3f})")
        data = self._transport(path, body)
        cost = float(data.get("cost") or 0.0)
        self.spent_usd += cost
        entry = {"label": label or path, "path": path, "cost_usd": cost, "cache": False,
                 "ok": succeeded(data), "time": time.strftime("%Y-%m-%d %H:%M")}
        self.calls.append(entry)
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(f"| {entry['time']} | {entry['label']} | `{path}` | {cost:.4f} | "
                        f"{'ok' if entry['ok'] else 'error'} |\n")
        if not succeeded(data):
            raise DFSError(f"{label or path}: status {data.get('status_code')}, task status "
                           f"{[t.get('status_code') for t in data.get('tasks') or [] if t]}")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_path(path, body).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        return data

    def _market(self, **extra) -> dict:
        return {"location_code": self.location_code, "language_code": self.language_code, **extra}

    # ---- the four calls ------------------------------------------------
    def search_volume(self, keywords: list[str], **kw) -> dict:
        body = [self._market(keywords=list(keywords))]
        return self.call("/keywords_data/google_ads/search_volume/live", body, "search volume", **kw)

    def keyword_ideas(self, seed: str, limit: int = 50, **kw) -> dict:
        body = [self._market(keywords=[seed], limit=limit)]
        return self.call("/dataforseo_labs/google/keyword_ideas/live", body, f"ideas: {seed}", **kw)

    def serp(self, keyword: str, depth: int = 10, **kw) -> dict:
        body = [self._market(keyword=keyword, device="desktop", depth=depth)]
        return self.call("/serp/google/organic/live/advanced", body, f"serp: {keyword}", **kw)

    def ranked_keywords(self, domain: str, limit: int = 100, **kw) -> dict:
        body = [self._market(target=domain, limit=limit)]
        return self.call("/dataforseo_labs/google/ranked_keywords/live", body, f"ranked: {domain}", **kw)


# ---- small readers used by run.py --------------------------------------
def results(data: dict) -> list:
    return [r for t in (data.get("tasks") or []) if t for r in (t.get("result") or []) if r]


def serp_top(data: dict, n: int = 10) -> dict:
    """Organic top n plus the SERP features present (AI overview, PAA, video ...)."""
    res = results(data)
    if not res:
        return {"organic": [], "features": [], "empty": True}
    items = res[0].get("items") or []
    organic = [{"pos": i.get("rank_group"), "domain": i.get("domain"), "url": i.get("url"),
                "title": i.get("title")} for i in items if i.get("type") == "organic"][:n]
    features = sorted({i.get("type") for i in items if i.get("type") and i.get("type") != "organic"})
    return {"organic": organic, "features": features, "empty": not organic}


def volumes(data: dict) -> dict:
    out = {}
    for r in results(data):
        if isinstance(r, dict) and r.get("keyword"):
            out[r["keyword"]] = {"volume": r.get("search_volume"), "competition": r.get("competition"),
                                 "cpc": r.get("cpc")}
    return out


def ranked(data: dict) -> list:
    res = results(data)
    items = (res[0].get("items") or []) if res else []
    return [{"keyword": (i.get("keyword_data") or {}).get("keyword"),
             "pos": ((i.get("ranked_serp_element") or {}).get("serp_item") or {}).get("rank_group"),
             "url": ((i.get("ranked_serp_element") or {}).get("serp_item") or {}).get("url")} for i in items]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["check", "volume", "ideas", "serp", "ranked"], nargs="?", default="check")
    ap.add_argument("arg", nargs="*", help="keyword(s), seed, or domain")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--location", type=int, default=2840)
    ap.add_argument("--language", default="en")
    ap.add_argument("--cache", default=".cache/dfs")
    ap.add_argument("--cap", type=float, default=0.5)
    a = ap.parse_args()
    client = DFS(a.cache, a.cap, a.location, a.language)
    try:
        if a.check or a.what == "check":
            data = client._transport("/appendix/user_data", None)
            res = results(data)
            print(json.dumps({"access_ok": succeeded(data), "cost_usd": data.get("cost"),
                              "balance_usd": (res[0].get("money") or {}).get("balance") if res else None}))
            return 0 if succeeded(data) else 1
        if not a.arg:
            ap.error("give a keyword, seed or domain")
        fn = {"volume": lambda: client.search_volume(a.arg), "ideas": lambda: client.keyword_ideas(a.arg[0]),
              "serp": lambda: client.serp(" ".join(a.arg)), "ranked": lambda: client.ranked_keywords(a.arg[0])}
        data = fn[a.what]()
        reader = {"volume": volumes, "serp": serp_top, "ranked": ranked, "ideas": results}[a.what]
        print(json.dumps(reader(data), ensure_ascii=False, indent=1)[:20000])
        print(f"cost this run: ${client.spent_usd:.4f}", file=sys.stderr)
        return 0
    except (DFSError, CapReached) as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
