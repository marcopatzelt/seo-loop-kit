import tempfile
import unittest
from pathlib import Path

from seoloop import gate

GOOD = """---
title: "Grill me skill: what it does and how to run it"
description: "The grill-me skill makes Claude interview you about a plan before it writes code. What it does, how to install it, and when to use it."
keyword: "grill me skill"
draft: true
---

# Grill me skill, explained

The grill me skill turns Claude into an interviewer that questions your plan before any code is written.

## Install
"""


def write(dirpath: Path, name: str, text: str) -> Path:
    p = dirpath / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def names_failed(checks):
    return {c.name for c in checks if not c.ok}


class GateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_good_page_passes(self):
        p = write(self.dir, "grill-me.md", GOOD)
        checks = gate.check_page(p, self.dir)
        self.assertTrue(gate.passed(checks), [c.line() for c in checks])

    def test_title_over_60_fails(self):
        p = write(self.dir, "a.md", GOOD.replace('title: "Grill me skill: what it does and how to run it"',
                                                 'title: "Grill me skill: what it does, how to install it and how to run it well"'))
        self.assertIn("title length", names_failed(gate.check_page(p, self.dir)))

    def test_title_exactly_60_passes(self):
        title = "Grill me skill " + "x" * 45
        self.assertEqual(len(title), 60)
        p = write(self.dir, "a.md", GOOD.replace("Grill me skill: what it does and how to run it", title))
        self.assertNotIn("title length", names_failed(gate.check_page(p, self.dir)))

    def test_description_over_155_fails(self):
        p = write(self.dir, "a.md", GOOD.replace("when to use it.", "when to use it. " + "y" * 40))
        self.assertIn("description length", names_failed(gate.check_page(p, self.dir)))

    def test_empty_description_fails(self):
        p = write(self.dir, "a.md", GOOD.replace('description: "The grill', 'description: ""\nx: "The grill'))
        self.assertIn("description length", names_failed(gate.check_page(p, self.dir)))

    def test_new_noindex_fails(self):
        p = write(self.dir, "a.md", GOOD.replace("draft: true", 'draft: true\nrobots: "noindex, follow"'))
        self.assertIn("no new noindex", names_failed(gate.check_page(p, self.dir)))

    def test_existing_noindex_is_not_new(self):
        text = GOOD.replace("draft: true", 'draft: true\nrobots: "noindex"')
        p = write(self.dir, "a.md", text)
        self.assertNotIn("no new noindex", names_failed(gate.check_page(p, self.dir, previous_text=text)))

    def test_meta_noindex_in_body_fails(self):
        p = write(self.dir, "a.md", GOOD + '\n<meta name="robots" content="noindex">\n')
        self.assertIn("no new noindex", names_failed(gate.check_page(p, self.dir)))

    def test_keyword_missing_from_h1_and_first_paragraph(self):
        text = GOOD.replace("# Grill me skill, explained", "# Interview mode for Claude").replace(
            "The grill me skill turns", "This turns")
        failed = names_failed(gate.check_page(write(self.dir, "a.md", text), self.dir))
        self.assertIn("keyword in H1", failed)
        self.assertIn("keyword in first paragraph", failed)
        self.assertNotIn("keyword in title", failed)

    def test_keyword_match_ignores_hyphens_and_case(self):
        text = GOOD.replace("# Grill me skill, explained", "# The Grill-Me Skill")
        self.assertNotIn("keyword in H1", names_failed(gate.check_page(write(self.dir, "a.md", text), self.dir)))

    def test_h1_from_frontmatter_wins(self):
        text = GOOD.replace("draft: true", 'draft: true\nh1: "Something else"')
        self.assertIn("keyword in H1", names_failed(gate.check_page(write(self.dir, "a.md", text), self.dir)))

    def test_missing_frontmatter(self):
        p = write(self.dir, "a.md", "# Just a heading\n")
        self.assertEqual(names_failed(gate.check_page(p, self.dir)), {"frontmatter"})

    def test_duplicate_keyword_fails(self):
        write(self.dir, "old.md", GOOD.replace("Grill me skill: what it does and how to run it", "Older grill me skill page"))
        p = write(self.dir, "new.md", GOOD)
        self.assertIn("no duplicate page", names_failed(gate.check_page(p, self.dir)))

    def test_duplicate_title_fails(self):
        write(self.dir, "old.md", GOOD.replace('keyword: "grill me skill"', 'keyword: "something else"'))
        p = write(self.dir, "new.md", GOOD)
        self.assertIn("no duplicate page", names_failed(gate.check_page(p, self.dir)))

    def test_translation_with_same_slug_is_not_a_duplicate(self):
        other = GOOD.replace("Grill me skill: what it does and how to run it", "Grill-me-Skill auf Deutsch").replace(
            '"grill me skill"', '"grill me skill deutsch"')
        write(self.dir, "de/grill-me.md", other)
        p = write(self.dir, "en/grill-me.md", GOOD)
        self.assertNotIn("no duplicate page", names_failed(gate.check_page(p, self.dir)))

    def test_build_skipped_without_command_is_recorded(self):
        c = gate.run_build("", self.dir)
        self.assertTrue(c.ok)
        self.assertIn("skipped", c.detail)

    def test_build_failure(self):
        import sys
        c = gate.run_build(f'"{sys.executable}" -c "import sys; sys.exit(3)"', self.dir)
        self.assertFalse(c.ok)
        self.assertIn("exit 3", c.detail)


if __name__ == "__main__":
    unittest.main()
