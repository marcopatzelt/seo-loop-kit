import datetime as dt
import unittest
from pathlib import Path

from seoloop.board import Board, parse_task

TEMPLATE = Path(__file__).resolve().parents[1] / "board.md"

SAMPLE = """# SEO loop board

Notes for humans stay here.

## Open

- [T-003] new-page | keyword: grill me skill | target: /skills/grill-me | opened: 2026-10-22 | why: 12,100/month (US, 22.10.2026)

## Shipped

- [T-001] snippet | keyword: loop engineering | target: /guides/loop-engineering | shipped: 2026-10-01 | verify: 2026-10-22
- [T-002] new-page | keyword: claude code loops | shipped: 2026-10-10 | verify: 2026-10-31

## Due for verify

(none)

## Rejected

- [T-004] new-page | keyword: archify | rejected: 2026-10-01 | reason: critic 14/20 after rewrite
"""


class BoardTest(unittest.TestCase):
    def test_parse_sections(self):
        b = Board.parse(SAMPLE)
        self.assertEqual([t.id for t in b.in_section("open")], ["T-003"])
        self.assertEqual([t.id for t in b.in_section("shipped")], ["T-001", "T-002"])
        self.assertEqual(b.in_section("due"), [])
        self.assertEqual(b.in_section("rejected")[0].get("reason"), "critic 14/20 after rewrite")

    def test_fields_and_dates(self):
        t = Board.parse(SAMPLE).find("T-003")
        self.assertEqual(t.type, "new-page")
        self.assertEqual(t.get("why"), "12,100/month (US, 22.10.2026)")
        self.assertEqual(t.date("opened"), dt.date(2026, 10, 22))
        self.assertIsNone(t.date("nope"))

    def test_value_with_colon_survives(self):
        t = parse_task("T-9", "new-page | why: source: https://example.com/a | keyword: x")
        self.assertEqual(t.get("why"), "source: https://example.com/a")

    def test_line_without_type(self):
        t = parse_task("T-9", "keyword: x | opened: 2026-01-01")
        self.assertEqual(t.type, "task")
        self.assertEqual(t.get("keyword"), "x")

    def test_mark_due_moves_only_due_tasks(self):
        b = Board.parse(SAMPLE)
        moved = b.mark_due(dt.date(2026, 10, 22))
        self.assertEqual([t.id for t in moved], ["T-001"])
        self.assertEqual([t.id for t in b.in_section("due")], ["T-001"])
        self.assertEqual([t.id for t in b.in_section("shipped")], ["T-002"])

    def test_add_skips_duplicate_keyword(self):
        b = Board.parse(SAMPLE)
        self.assertIsNone(b.add("new-page", dt.date(2026, 10, 22), keyword="Grill-Me Skill"))
        t = b.add("new-page", dt.date(2026, 10, 22), keyword="taste skill", why="5,400/month")
        self.assertEqual(t.id, "T-005")
        self.assertEqual(t.get("opened"), "2026-10-22")

    def test_rejected_keyword_is_not_reopened_by_add(self):
        b = Board.parse(SAMPLE)
        # rejected tasks do not block a fresh attempt: keywords() only looks at open, shipped, due
        self.assertIsNotNone(b.add("new-page", dt.date(2026, 10, 22), keyword="archify"))

    def test_round_trip_is_stable(self):
        b = Board.parse(SAMPLE)
        once = b.render()
        self.assertEqual(Board.parse(once).render(), once)
        self.assertIn("Notes for humans stay here.", once)

    def test_pipe_in_value_is_escaped(self):
        b = Board()
        b.add("new-page", dt.date(2026, 10, 22), keyword="x", why="a | b")
        again = Board.parse(b.render())
        self.assertEqual(again.tasks[0].get("why"), "a / b")

    def test_template_parses_empty(self):
        b = Board.parse(TEMPLATE.read_text(encoding="utf-8"))
        self.assertEqual(b.tasks, [])


if __name__ == "__main__":
    unittest.main()
