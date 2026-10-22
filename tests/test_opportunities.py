import unittest

from seoloop import opportunities as op

PAGES = [("content/seo-audit.md", "SEO audit for small sites", "seo audit"),
         ("content/grill-me.md", "Grill me skill", "grill me skill")]


def row(page, query, imp, pos, clicks=0, ctr=None):
    return {"keys": [page, query], "impressions": imp, "position": pos, "clicks": clicks,
            "ctr": ctr if ctr is not None else (clicks / imp if imp else 0)}


class OpportunityTest(unittest.TestCase):
    def test_striking_distance(self):
        o = op.find([row("/seo-audit", "seo audit", 120, 12.4)], [], PAGES)
        self.assertEqual([x["query"] for x in o["striking"]], ["seo audit"])
        self.assertEqual(o["gap"], [])

    def test_snippet_needs_top10_and_low_ctr(self):
        o = op.find([row("/grill-me", "grill me skill", 400, 4.0, clicks=2)], [], PAGES)
        self.assertEqual(o["snippet"][0]["task"], "snippet")
        o = op.find([row("/grill-me", "grill me skill", 400, 4.0, clicks=20)], [], PAGES)
        self.assertEqual(o["snippet"], [])

    def test_content_gap_when_no_page_fits(self):
        o = op.find([row("/seo-audit", "matt pocock skills", 90, 14.0)], [], PAGES)
        self.assertEqual(o["gap"][0]["query"], "matt pocock skills")
        self.assertIsNone(o["gap"][0]["fits"])
        self.assertEqual(o["striking"], [])

    def test_content_gap_when_best_page_ranks_far_back(self):
        o = op.find([row("/seo-audit", "seo audit", 200, 34.0)], [], PAGES)
        self.assertEqual(o["gap"][0]["fits"], "content/seo-audit.md")

    def test_small_queries_are_ignored(self):
        o = op.find([row("/x", "rare query here", 10, 15.0)], [], PAGES)
        self.assertFalse(any(o.values()))

    def test_decay(self):
        o = op.find([row("/seo-audit", "seo audit", 300, 5.0, clicks=10)], [{"keys": ["/seo-audit"], "clicks": 40}], PAGES)
        self.assertEqual(o["decay"][0]["drop"], 0.75)
        o = op.find([row("/seo-audit", "seo audit", 300, 5.0, clicks=35)], [{"keys": ["/seo-audit"], "clicks": 40}], PAGES)
        self.assertEqual(o["decay"], [])

    def test_markdown_names_task_types(self):
        o = op.find([row("/seo-audit", "seo audit", 120, 12.4), row("/seo-audit", "matt pocock skills", 90, 14.0)], [], PAGES)
        md = op.markdown(o, "2026-09-20", "2026-10-18")
        self.assertIn("`improve`", md)
        self.assertIn("`new-page`", md)


if __name__ == "__main__":
    unittest.main()
