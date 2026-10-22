I graded the Archify page at 17 of 20, which is the lowest passing score. It's honest and every claim has a source. It's thin on what most searchers came for, which is how to use the tool.

**1. Search intent: 3/5**
- **What works:** The first paragraph answers "what is Archify". The search results all point to this one tool (the tt-a1i repo, its roadmap, agentconn, a video, a Medium post, and hands-on posts on note.com and Reddit), so the keyword isn't ambiguous.
- **Gap 1:** The top results that aren't directory listings are mostly people trying it out, plus the repo itself. The page says "We have not tested Archify ourselves" and "We do not repeat them here because they change." That leaves out how you run it and what the output looks like.
- **Fix:** Add a short "How to run it" section: the install command from the repo README, one example prompt, and the output format (HTML, Mermaid, etc.). Date-stamp it with a link to the repo for changes.
- **Gap 2:** The H1 and title push "where it fits in a loop", which is the site's angle, not the searcher's. Consider "Archify: what it does, how to run it, when to use it".

**2. Facts with source: 5/5**
- Each claim matches a listed source: idea, plan or codebase to diagram (repo); listed as an agent skill (agentconn); interactive codebase diagrams (video and Medium titles); public roadmap (ROADMAP.md).
- The 1300 monthly searches in the frontmatter matches data.md.
- No invented numbers. Opinions are labelled as such, for example "This table is our suggested policy for reviewers, not a feature of Archify."
- Caveat: I can't open web pages, so I checked the claims only against the result titles in data.md. They all match.

**3. Copy rules: 4/5**
- Plain words, no hype, no em dashes, mostly short sentences. The title is about 49 characters and the description is about 150, both within limits.
- Small edit: the last sentence of "Make it a habit" is long and a bit generic ("An Archify step would follow the same pattern: trigger on..., produce..., and have..."). Split it into two sentences.

**4. Internal links and schema: 3/3**
- Three internal links, all to pages that exist (/loops/plan-grill-loop, /loops/ui-taste-loop, /loops/seo-loop), with descriptive anchors.
- The existing pages use no structured data, so none is expected here.

**5. Own value vs the top 10: 2/3**
- **What works:** The "When to regenerate the diagram" table and the "before the tickets" check in the plan grill loop are original. Nothing in the top 10 offers either.
- **Gap:** Both are guesses about how the tool would be used, with no example behind them.
- **Fix:** Add one worked example: run Archify on a small public repo (or the seo-loop-kit repo) before and after a structural PR, and show the two diagrams or describe the difference. That would also close the "we have not tested it" gap from criterion 1.

```json
{"intent": 3, "facts": 5, "copy": 4, "links_schema": 3, "own_value": 2, "total": 17,
 "verdict": "pass", "notes": ["Intent: add a short 'How to run it' section with the install command from the repo README, one example prompt and the output format, date-stamped and linked to the repo; the sentence 'We do not repeat them here because they change' leaves the main how-to question unanswered.", "Intent: consider retitling the H1/title toward the searcher, e.g. 'Archify: what it does, how to run it, when to use it', rather than leading with the site's loop angle.", "Own value: replace 'We have not tested Archify ourselves' with one worked example: run it on a small public repo before and after a structural PR and show or describe the diagram difference, which backs up the regenerate table.", "Copy: split the last sentence of 'Make it a habit' ('An Archify step would follow the same pattern: ...') into two shorter sentences."]}
```