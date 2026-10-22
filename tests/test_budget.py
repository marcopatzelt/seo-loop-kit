import json
import tempfile
import unittest
from pathlib import Path

import dfs
from seoloop.budget import RunBudget


class BudgetTest(unittest.TestCase):
    def test_stops_at_usd(self):
        b = RunBudget(max_usd=8.0, max_tasks=3)
        b.charge("builder", 5.0)
        self.assertIsNone(b.stop_reason())
        b.charge("critic", 3.0)
        self.assertIn("budget", b.stop_reason())
        self.assertEqual(b.remaining_usd, 0.0)

    def test_stops_at_three_tasks(self):
        b = RunBudget(max_usd=8.0, max_tasks=3)
        for _ in range(3):
            self.assertIsNone(b.stop_reason())
            b.task_finished()
        self.assertIn("tasks", b.stop_reason())

    def test_can_afford(self):
        b = RunBudget(max_usd=1.0)
        b.charge("x", 0.9)
        self.assertTrue(b.can_afford(0.1))
        self.assertFalse(b.can_afford(0.2))

    def test_none_cost_counts_as_zero(self):
        b = RunBudget()
        b.charge("x", None)
        self.assertEqual(b.spent_usd, 0.0)


def fake_response(cost, items=None):
    return {"status_code": 20000, "cost": cost, "tasks_error": 0,
            "tasks": [{"status_code": 20000, "result": [{"items": items or []}]}]}


class DataForSEOCapTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.calls = []

        def transport(path, body):
            self.calls.append(path)
            return fake_response(0.002)
        self.client = dfs.DFS(Path(self.tmp.name), cap_usd=0.01, location_code=2840, language_code="en",
                              transport=transport)

    def tearDown(self):
        self.tmp.cleanup()

    def test_cap_refuses_next_call(self):
        # each call costs 0.002, the estimate is 0.004: a call runs only if spent + 0.004 <= 0.01
        for kw in "abcd":
            self.client.serp(kw)  # spent before: 0, .002, .004, .006
        with self.assertRaises(dfs.CapReached):
            self.client.serp("e")  # .008 + .004 > .01
        self.assertEqual(len(self.calls), 4)
        self.assertAlmostEqual(self.client.spent_usd, 0.008)

    def test_cache_hit_is_free_and_skips_network(self):
        self.client.serp("a")
        self.client.serp("a")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.client.calls[-1]["cache"], True)

    def test_cache_only_miss_raises(self):
        with self.assertRaises(dfs.CapReached):
            self.client.serp("zzz", cache_only=True)
        self.assertEqual(self.calls, [])

    def test_market_is_always_sent(self):
        seen = {}

        def transport(path, body):
            seen.update(body[0])
            return fake_response(0.0)
        c = dfs.DFS(Path(self.tmp.name) / "x", 1.0, 2826, "en", transport=transport)
        c.ranked_keywords("example.com")
        self.assertEqual((seen["location_code"], seen["language_code"]), (2826, "en"))

    def test_task_error_is_not_cached_but_charged(self):
        def transport(path, body):
            return {"status_code": 20000, "cost": 0.002, "tasks": [{"status_code": 40501}]}
        c = dfs.DFS(Path(self.tmp.name) / "e", 1.0, 2840, "en", transport=transport)
        with self.assertRaises(dfs.DFSError):
            c.serp("bad")
        self.assertAlmostEqual(c.spent_usd, 0.002)
        self.assertFalse(list((Path(self.tmp.name) / "e").glob("*.json")) if (Path(self.tmp.name) / "e").exists() else [])

    def test_credentials_never_in_error(self):
        with self.assertRaises(dfs.DFSError) as ctx:
            dfs.credentials({"DATAFORSEO_LOGIN": "user@example.com"})
        self.assertNotIn("user@example.com", str(ctx.exception))

    def test_serp_reader(self):
        items = [{"type": "ai_overview"}, {"type": "organic", "rank_group": 1, "domain": "a.com", "url": "u", "title": "t"}]
        top = dfs.serp_top(fake_response(0, items))
        self.assertEqual(top["features"], ["ai_overview"])
        self.assertEqual(top["organic"][0]["domain"], "a.com")
        self.assertFalse(top["empty"])
        json.dumps(top)


if __name__ == "__main__":
    unittest.main()
