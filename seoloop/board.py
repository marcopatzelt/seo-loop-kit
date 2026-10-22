"""The task board: the loop's memory, kept as plain Markdown.

Four sections, one task per line:

    ## Open
    - [T-003] new-page | keyword: grill me skill | target: /skills/grill-me | opened: 2026-10-22 | why: ...

    ## Shipped
    - [T-001] snippet | keyword: ... | shipped: 2026-10-01 | verify: 2026-10-22

    ## Due for verify
    ## Rejected

The line format is `- [ID] type | key: value | key: value`. Values may not
contain ` | `. Unknown sections and free text outside the four sections are
kept as they are when the board is written back.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path

SECTIONS = {"open": "Open", "shipped": "Shipped", "due": "Due for verify", "rejected": "Rejected"}
_HEADING = {v.lower(): k for k, v in SECTIONS.items()}
_TASK = re.compile(r"^- \[(?P<id>[A-Za-z0-9_-]+)\]\s*(?P<rest>.*)$")


@dataclass
class Task:
    id: str
    type: str
    fields: dict = field(default_factory=dict)
    section: str = "open"

    def get(self, key, default=""):
        return self.fields.get(key, default)

    def date(self, key) -> dt.date | None:
        value = self.fields.get(key)
        try:
            return dt.date.fromisoformat(value) if value else None
        except ValueError:
            return None

    def to_line(self) -> str:
        parts = [f"- [{self.id}] {self.type}"]
        for k, v in self.fields.items():
            v = str(v).replace(" | ", " / ").replace("\n", " ").strip()
            parts.append(f"{k}: {v}")
        return " | ".join(parts)


@dataclass
class Board:
    title: str = "# SEO loop board"
    preamble: list = field(default_factory=list)
    tasks: list = field(default_factory=list)

    # ---- reading -------------------------------------------------------
    @classmethod
    def parse(cls, text: str) -> "Board":
        board = cls(preamble=[])
        section = None
        seen_title = False
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("# ") and not seen_title:
                board.title, seen_title = s, True
                continue
            if s.startswith("## "):
                section = _HEADING.get(s[3:].strip().lower())
                if section is None:
                    board.preamble.append(line)
                continue
            m = _TASK.match(s)
            if m and section:
                board.tasks.append(parse_task(m.group("id"), m.group("rest"), section))
            elif section is None:
                board.preamble.append(line)
            # free text inside a known section is dropped on purpose: the
            # section belongs to the loop.
        while board.preamble and not board.preamble[-1].strip():
            board.preamble.pop()
        while board.preamble and not board.preamble[0].strip():
            board.preamble.pop(0)
        return board

    @classmethod
    def load(cls, path: str | Path) -> "Board":
        p = Path(path)
        return cls.parse(p.read_text(encoding="utf-8")) if p.exists() else cls()

    def in_section(self, section: str) -> list:
        return [t for t in self.tasks if t.section == section]

    def find(self, task_id: str) -> Task | None:
        return next((t for t in self.tasks if t.id == task_id), None)

    def keywords(self, sections=("open", "shipped", "due")) -> set:
        return {norm(t.get("keyword")) for t in self.tasks if t.section in sections and t.get("keyword")}

    def next_id(self) -> str:
        nums = [int(m.group(1)) for t in self.tasks if (m := re.fullmatch(r"T-(\d+)", t.id))]
        return f"T-{(max(nums) + 1 if nums else 1):03d}"

    # ---- changing ------------------------------------------------------
    def add(self, type_: str, today: dt.date, **fields) -> Task | None:
        """Add an open task. Returns None if the keyword is already on the board."""
        kw = norm(fields.get("keyword", ""))
        if kw and kw in self.keywords():
            return None
        ordered = {"keyword": fields.pop("keyword", "")}
        ordered.update(fields)
        ordered.setdefault("opened", today.isoformat())
        task = Task(self.next_id(), type_, ordered, "open")
        self.tasks.append(task)
        return task

    def move(self, task: Task, section: str, **fields) -> None:
        if section not in SECTIONS:
            raise ValueError(f"unknown section {section}")
        task.section = section
        task.fields.update({k: str(v) for k, v in fields.items()})

    def mark_due(self, today: dt.date) -> list:
        """Move shipped tasks whose verify date has come into 'Due for verify'."""
        moved = []
        for t in self.in_section("shipped"):
            d = t.date("verify")
            if d and d <= today and not t.get("verified"):
                self.move(t, "due")
                moved.append(t)
        return moved

    # ---- writing -------------------------------------------------------
    def render(self) -> str:
        out = [self.title, ""]
        if self.preamble:
            out += self.preamble + [""]
        for key, heading in SECTIONS.items():
            out.append(f"## {heading}")
            out.append("")
            tasks = self.in_section(key)
            out += [t.to_line() for t in tasks] if tasks else ["(none)"]
            out.append("")
        return "\n".join(out).rstrip() + "\n"

    def save(self, path: str | Path) -> None:
        Path(path).write_text(self.render(), encoding="utf-8")


def parse_task(task_id: str, rest: str, section: str = "open") -> Task:
    parts = [p.strip() for p in rest.split(" | ") if p.strip()]
    if parts and ":" not in parts[0]:
        type_, field_parts = parts[0], parts[1:]
    else:
        type_, field_parts = "task", parts
    fields = {}
    for p in field_parts:
        if ":" in p:
            k, v = p.split(":", 1)
            fields[k.strip()] = v.strip()
    return Task(task_id, type_, fields, section)


def norm(s: str) -> str:
    return re.sub(r"[\s\-_]+", " ", (s or "").lower()).strip()
