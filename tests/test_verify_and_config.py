import datetime as dt
import tempfile
import unittest
from pathlib import Path

import run
import verify
from seoloop.board import Board
from seoloop.config import load_config, parse_yaml_subset

EXAMPLE = Path(__file__).resolve().parents[1] / "config.example.yaml"


class VerifyRuleTest(unittest.TestCase):
    def test_ranked_but_no_clicks_reopens_as_snippet(self):
        verdict, kind, reason = verify.judge({"clicks": 0, "impressions": 150, "ctr": 0.0, "position": 8.0})
        self.assertEqual((verdict, kind), ("reopen", "snippet"))
        self.assertIn("ranked but no clicks", reason)

    def test_ctr_just_under_half_percent(self):
        self.assertEqual(verify.judge({"clicks": 1, "impressions": 250, "ctr": 0.004, "position": 6})[1], "snippet")

    def test_ctr_at_half_percent_is_fine(self):
        self.assertEqual(verify.judge({"clicks": 1, "impressions": 200, "ctr": 0.005, "position": 6})[0], "verified")

    def test_under_100_impressions_is_not_the_snippet_rule(self):
        verdict, kind, _ = verify.judge({"clicks": 0, "impressions": 90, "ctr": 0.0, "position": 8})
        self.assertNotEqual(kind, "snippet")
        self.assertEqual(verdict, "verified")  # top 10 without enough impressions to judge the snippet

    def test_position_11_is_not_the_snippet_rule(self):
        self.assertNotEqual(verify.judge({"clicks": 0, "impressions": 500, "ctr": 0.0, "position": 11})[1], "snippet")

    def test_invisible(self):
        self.assertEqual(verify.judge({"clicks": 0, "impressions": 12, "ctr": 0, "position": 45})[1], "improve")
        self.assertEqual(verify.judge(None)[1], "improve")

    def test_window_respects_search_console_lag(self):
        start, end = verify.window(dt.date(2026, 10, 1), dt.date(2026, 10, 22))
        self.assertEqual(start, dt.date(2026, 10, 2))
        self.assertEqual(end, dt.date(2026, 10, 19))

    def test_run_applies_verdicts_to_board(self):
        class FakeGSC:
            def page_rows(self, start, end, url):
                return {"clicks": 0, "impressions": 300, "ctr": 0.0, "position": 4.2}
        with tempfile.TemporaryDirectory() as tmp:
            loop = Path(tmp)
            (loop / "board.md").write_text(
                "# b\n\n## Shipped\n\n- [T-001] new-page | keyword: k | target: /k | shipped: 2026-10-01 | verify: 2026-10-22\n",
                encoding="utf-8")
            cfg = {"_loop_dir": loop, "site_url": "https://example.com", "verify": {"after_days": 21}}
            report = verify.run(cfg, dt.date(2026, 10, 22), apply=True, client=FakeGSC())
            self.assertEqual(report[0]["url"], "https://example.com/k")
            t = Board.load(loop / "board.md").find("T-001")
            self.assertEqual((t.section, t.type), ("open", "snippet"))
            self.assertIn("ranked but no clicks", t.get("why"))


class ConfigTest(unittest.TestCase):
    def test_subset_parser(self):
        data = parse_yaml_subset('a: 1\nb: "x # not a comment"\nc:\n  d: 2.5\n  e: true\nf:\n  - one\n  - "two"\ng: [x, y]\n')
        self.assertEqual(data, {"a": 1, "b": "x # not a comment", "c": {"d": 2.5, "e": True},
                                "f": ["one", "two"], "g": ["x", "y"]})

    def test_example_config_loads(self):
        cfg = load_config(EXAMPLE)
        self.assertEqual(cfg["budget"]["max_usd_per_run"], 8)
        self.assertEqual(cfg["budget"]["max_tasks_per_run"], 3)
        self.assertEqual(cfg["critic"]["pass_score"], 17)
        self.assertTrue(cfg["_content_dir"].is_absolute())

    def test_missing_site_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "c.yaml"
            p.write_text("content_dir: x\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_config(p)


class CriticParseTest(unittest.TestCase):
    def test_takes_last_block_and_recomputes_total(self):
        text = ('Notes {not json}.\n```json\n{"intent": 5, "facts": 9, "copy": 4, "links_schema": 3, '
                '"own_value": 3, "total": 20, "verdict": "pass", "notes": ["x"]}\n```')
        s = run.parse_critic(text)
        self.assertEqual(s["facts"], 5)  # capped
        self.assertEqual(s["total"], 20)

    def test_miscounted_total_cannot_pass(self):
        s = run.parse_critic('{"intent": 3, "facts": 3, "copy": 3, "links_schema": 2, "own_value": 2, "total": 19}')
        self.assertEqual(s["total"], 13)

    def test_no_block(self):
        self.assertIsNone(run.parse_critic("I liked it."))


class GuardTest(unittest.TestCase):
    def test_secret_regex(self):
        for bad in ("/x/.env", "/x/.env.local", "/x/secrets/a.json", "/x/gsc-key.json", "/x/id_rsa", "/x/a.pem"):
            self.assertTrue(run.SECRET.search(bad), bad)
        for ok in ("/x/content/grill-me-skill.md", "/x/board.md", "/x/runs/2026-10-22-seo/data.md"):
            self.assertFalse(run.SECRET.search(ok), ok)


if __name__ == "__main__":
    unittest.main()
