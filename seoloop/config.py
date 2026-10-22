"""Read config.yaml without a YAML dependency.

Supports the subset the kit uses: `key: value` scalars, one level of nested
mappings, and `- item` lists of scalars. Comments start with `#`.
If PyYAML is installed it is used instead, so a richer file still works.
"""
from __future__ import annotations

import re
from pathlib import Path

DEFAULTS = {
    "site_url": "",
    "root": ".",
    "content_dir": "src/content",
    "loop_dir": "loops/seo-loop",
    "page_extension": ".md",
    "language": "en",
    "location_code": 2840,
    "language_code": "en",
    "target_keywords": [],
    "build_command": "",
    "copy_rules": "",
    "budget": {"max_usd_per_run": 8.0, "max_tasks_per_run": 3, "max_pages_per_run": 3,
               "dataforseo_cap_usd": 0.5},
    "models": {"builder": "claude-sonnet-5-5", "critic": "claude-opus-5-5", "advisor": ""},
    "critic": {"pass_score": 17, "max_rewrites": 1},
    "verify": {"after_days": 21, "gsc_property": "", "gsc_key_env": "GSC_KEY_FILE"},
    "find": {},  # Search Console thresholds for step 02, see seoloop/opportunities.py DEFAULTS
}


def _scalar(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if s[0] in "\"'":
        end = s.find(s[0], 1)
        if end == -1:
            raise ValueError(f"Unclosed quote: {raw!r}")
        return s[1:end]
    s = re.split(r"\s+#", s, maxsplit=1)[0].strip()
    low = s.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "~"):
        return None
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        return [_scalar(p) for p in inner.split(",")] if inner else []
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"-?\d+\.\d*", s):
        return float(s)
    return s


def parse_yaml_subset(text: str) -> dict:
    data: dict = {}
    parent: str | None = None  # top-level key whose block we are inside
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        body = line.strip()
        if indent == 0:
            m = re.match(r"^([A-Za-z0-9_]+):(.*)$", body)
            if not m:
                raise ValueError(f"config line {n}: expected 'key: value'")
            key, rest = m.group(1), m.group(2)
            if rest.strip() and not rest.strip().startswith("#"):
                data[key] = _scalar(rest)
                parent = None
            else:
                data[key] = None  # filled by the block below
                parent = key
            continue
        if parent is None:
            raise ValueError(f"config line {n}: unexpected indentation")
        if body.startswith("- "):
            if data[parent] is None:
                data[parent] = []
            if not isinstance(data[parent], list):
                raise ValueError(f"config line {n}: list item inside a mapping")
            data[parent].append(_scalar(body[2:]))
            continue
        m = re.match(r"^([A-Za-z0-9_]+):(.*)$", body)
        if not m:
            raise ValueError(f"config line {n}: expected 'key: value'")
        if data[parent] is None:
            data[parent] = {}
        if not isinstance(data[parent], dict):
            raise ValueError(f"config line {n}: mapping entry inside a list")
        data[parent][m.group(1)] = _scalar(m.group(2))
    return {k: ({} if v is None else v) for k, v in data.items()}


def load_config(path: str | Path) -> dict:
    path = Path(path).resolve()
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
        raw = yaml.safe_load(text) or {}
    except ImportError:
        raw = parse_yaml_subset(text)
    cfg: dict = {}
    for key, default in DEFAULTS.items():
        value = raw.get(key, default)
        if isinstance(default, dict):
            merged = dict(default)
            merged.update(value or {})
            value = merged
        cfg[key] = value
    for key, value in raw.items():
        cfg.setdefault(key, value)
    root = (path.parent / str(cfg["root"])).resolve()
    cfg["_config_path"] = str(path)
    cfg["_root"] = root
    cfg["_content_dir"] = (root / cfg["content_dir"]).resolve()
    cfg["_loop_dir"] = (root / cfg["loop_dir"]).resolve()
    if not cfg["site_url"]:
        raise ValueError("config: site_url is required")
    return cfg
