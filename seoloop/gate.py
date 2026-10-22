"""Hard checks. Mechanical, no model, no opinion. See gate.md.

A page is a Markdown file with a frontmatter block:

    ---
    title: "Grill me skill: what it does and how to run it"
    description: "..."
    keyword: "grill me skill"
    h1: "..."            # optional; defaults to the first '# ' heading, then the title
    robots: "index"      # optional
    draft: true
    ---
    First paragraph ...
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

TITLE_MAX = 60
DESCRIPTION_MAX = 155


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""

    def line(self) -> str:
        return f"{'PASS' if self.ok else 'FAIL'} {self.name}" + (f": {self.detail}" if self.detail else "")


def parse_page(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).splitlines():
        mm = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if mm:
            v = mm.group(2).strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            fm[mm.group(1)] = v
    return fm, m.group(2)


def norm(s: str) -> str:
    return re.sub(r"[\s\-_:,.!?]+", " ", (s or "").lower()).strip()


def first_paragraph(body: str) -> str:
    for block in re.split(r"\n\s*\n", body):
        b = block.strip()
        if b and not b.startswith(("#", "<!--", "|", "```", ">", "- ", "* ", "!")):
            return b
    return ""


def h1_of(fm: dict, body: str) -> str:
    if fm.get("h1"):
        return fm["h1"]
    m = re.search(r"^# (.+)$", body, re.M)
    return m.group(1).strip() if m else fm.get("title", "")


def has_noindex(fm: dict, body: str) -> bool:
    robots = (fm.get("robots", "") + " " + fm.get("noindex", "")).lower()
    if "noindex" in robots or fm.get("noindex", "").lower() == "true":
        return True
    return bool(re.search(r"<meta[^>]+noindex", body, re.I))


def check_page(path: Path, content_dir: Path, previous_text: str | None = None,
               page_ext: str = ".md") -> list[Check]:
    """Run every content check on one page. `previous_text` is the page before
    this run (None for a new page), used for the 'no new noindex' rule."""
    text = Path(path).read_text(encoding="utf-8")
    fm, body = parse_page(text)
    checks: list[Check] = []
    if not fm:
        return [Check("frontmatter", False, "no --- block at the top")]

    title, desc, kw = fm.get("title", ""), fm.get("description", ""), fm.get("keyword", "")
    checks.append(Check("title length", 0 < len(title) <= TITLE_MAX, f"{len(title)} chars, max {TITLE_MAX}"))
    checks.append(Check("description length", 0 < len(desc) <= DESCRIPTION_MAX,
                        f"{len(desc)} chars, max {DESCRIPTION_MAX}"))

    was_noindex = False
    if previous_text is not None:
        was_noindex = has_noindex(*parse_page(previous_text))
    now_noindex = has_noindex(fm, body)
    checks.append(Check("no new noindex", not (now_noindex and not was_noindex),
                        "noindex added" if now_noindex and not was_noindex else ""))

    if not kw:
        checks.append(Check("keyword", False, "frontmatter 'keyword' missing"))
    else:
        k = norm(kw)
        for where, s in (("title", title), ("H1", h1_of(fm, body)), ("first paragraph", first_paragraph(body))):
            checks.append(Check(f"keyword in {where}", k in norm(s), f'"{kw}"'))

    checks.append(duplicate_check(Path(path), content_dir, title, kw, page_ext))
    return checks


def duplicate_check(path: Path, content_dir: Path, title: str, keyword: str, page_ext: str = ".md") -> Check:
    """No other page in the content dir may share the title or the target keyword.
    (Same slug in another folder is allowed: translations often share slugs.)"""
    path = path.resolve()
    clashes = []
    for other in Path(content_dir).rglob(f"*{page_ext}"):
        if other.resolve() == path:
            continue
        try:
            ofm, _ = parse_page(other.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        if title and norm(ofm.get("title", "")) == norm(title):
            clashes.append(f"{other.name}: same title")
        elif keyword and norm(ofm.get("keyword", "")) == norm(keyword):
            clashes.append(f"{other.name}: same keyword")
    return Check("no duplicate page", not clashes, "; ".join(clashes[:3]))


def run_build(command: str, cwd: Path, timeout: int = 900) -> Check:
    """'Build passes'. Without a build_command the check is recorded as skipped, not passed."""
    if not command:
        return Check("build passes", True, "skipped: no build_command in config")
    try:
        proc = subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return Check("build passes", False, f"timeout after {timeout}s")
    tail = (proc.stdout + proc.stderr).strip().splitlines()[-3:]
    return Check("build passes", proc.returncode == 0, f"exit {proc.returncode}" + (": " + " / ".join(tail) if proc.returncode else ""))


def passed(checks: list[Check]) -> bool:
    return all(c.ok for c in checks)
