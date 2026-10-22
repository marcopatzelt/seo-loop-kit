I graded the Archify page at **14/20, so it goes back for a rewrite.** The facts are careful and the links are good. But the page doesn't show how to use Archify, and it adds nothing the current top 10 lack.

**1. Search intent: 3/5**
- The first paragraph does answer "what is Archify". Good.
- The meta description promises "how to use it in a plan-to-tickets habit". The page doesn't deliver that: "For install steps, options and current features, use the repo itself… We do not repeat them here because they change." The top 10 for "archify" are the repo, the roadmap, a video demo and a hands-on note.com post ("I tried using 'Archify'…"). Searchers expect a walkthrough.
- **Fix:** add a short "How to run it" section. It should cover the install command and one example prompt, plus what comes out, taken from the repo README with a link and a "checked on 2026-10-22" note. Otherwise, take "how to use it" out of the description.

**2. Facts with source: 4/5**
- No invented numbers. The 1300 volume matches data.md. The idea/plan/codebase claim matches the repo title, the agent skill label matches agentconn, and the interactive diagram claim matches the video and Medium titles.
- One point off because "It is a skill for AI coding agents, not a standalone app" goes further than the sources. Agentconn only says "AI Agent Skill". **Fix:** drop "not a standalone app" or cite the README line that supports it.
- I had no web access, so I checked the source notes against the result titles in data.md, not the pages themselves. The builder should confirm the README actually says "idea, plan or codebase" before publishing.

**3. Copy rules: 3/4**
- No em dashes, no hype words, and the sentences are short. Good.
- "This page explains what that means in practice and where it can sit in a repeatable habit." is a filler meta sentence. **Fix:** delete it.
- The hedging piles up and reads templated: "Based on the public sources listed above:", "This is a suggested use, not a built-in step of that loop.", and "The sources above are descriptions, not benchmarks. We have not measured speed or accuracy and make no claim about either." **Fix:** keep one honest line ("We have not tested Archify ourselves.") and cut the rest.
- There's a bare URL in the body ("use the repo itself: https://github.com/tt-a1i/archify"). **Fix:** turn it into a link with a descriptive anchor, such as "the Archify repo on GitHub".

**4. Internal links and schema: 3/3**
- It has three relevant internal links with descriptive anchors: plan grill loop, UI taste loop and SEO loop. All three exist in content/loops.
- None of the existing pages use structured data, so nothing is missing there.
- Small fix: the frontmatter has no `url:` field, while every existing page has one. Add `url: "/archify"` or whatever the site uses for this kind of page.

**5. Own value vs the top 10: 1/3**
- The "two trigger points" idea (before tickets, after a structural PR) is the only original angle. It's speculative and thin, and the page admits it wasn't tried.
- There's no worked example, no diagram, no real output and no decision table. The note.com and YouTube results both show real use, which this page can't match as it stands.
- **Fix:** run Archify once on a real plan from the plan grill loop and show the input and the resulting diagram. Then add what had to be corrected by hand. Alternatively, add a small table of when a diagram helps and when it's noise (new module, rename, config-only PR) with a reason for each row.

```json
{"intent": 3, "facts": 4, "copy": 3, "links_schema": 3, "own_value": 1, "total": 14,
 "verdict": "rewrite", "notes": ["Intent: the description promises 'how to use it' but the page sends readers to the repo. Add a short 'How to run it' section (install command, one example prompt, what comes out) sourced from the README with a checked date, or remove 'how to use it' from the description.", "Facts: 'not a standalone app' goes further than the sources (agentconn only says 'AI Agent Skill'). Drop it or cite the README line. Before publishing, confirm the README actually says idea, plan or codebase; the critic only checked SERP titles.", "Copy: delete the filler sentence 'This page explains what that means in practice and where it can sit in a repeatable habit.'", "Copy: cut the stacked hedges ('Based on the public sources listed above:', 'This is a suggested use, not a built-in step of that loop.', 'The sources above are descriptions, not benchmarks...') down to one honest line such as 'We have not tested Archify ourselves.'", "Copy: replace the bare URL 'https://github.com/tt-a1i/archify' in the body with a link that has a descriptive anchor, such as 'the Archify repo on GitHub'.", "Frontmatter: add a url field (e.g. url: \"/archify\") to match the existing pages.", "Own value: add a worked example. Run Archify on a real spec from the plan grill loop and show the input, the diagram and what needed manual correction. Or add a decision table of PR types (new module, move, rename, config-only) saying when to regenerate the diagram and why. The note.com and YouTube results already show real use; this page shows none."]}
```