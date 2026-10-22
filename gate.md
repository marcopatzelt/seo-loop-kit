# Gate

Step 04 of the loop. Hard checks: mechanical, no model, no opinion. A page that fails any of them
never reaches the critic. The builder gets the failures and one attempt to fix them; if it still
fails, the page is moved out of the content dir into the run folder and the task goes to Rejected
with the failing checks as the reason.

Code: `seoloop/gate.py`. Tests: `tests/test_gate.py`.

| Check | Rule | Why |
| --- | --- | --- |
| **Build passes** | `build_command` from the config exits 0. Without a `build_command` the check is recorded as *skipped*, never as passed. | What ships is what search engines see. A broken build ships nothing. |
| **Title ≤ 60** | frontmatter `title`, 1 to 60 characters | Longer titles get cut in results. |
| **Description ≤ 155** | frontmatter `description`, 1 to 155 characters | Same for snippets. Empty is a fail. |
| **No new noindex** | no `noindex` in `robots`/`noindex` frontmatter or a `<meta>` tag, unless the page already had it before this run | One stray noindex removes a page from Google silently. |
| **Keyword in title, H1, first paragraph** | case and hyphen insensitive. H1 = frontmatter `h1`, else the first `# ` heading, else the title. | The cheapest relevance signal there is. Three separate checks, so the failure says where. |
| **No duplicate page** | no other page in the content dir has the same title or the same target keyword | Two pages on one keyword compete with each other. Same slug in a different folder (translations) is allowed. |

Before writing at all (step 03/04 in the builder prompt), a task is skipped if its keyword is
already on the board (Open, Shipped or Due for verify) or a page for it exists.

## Adapting it

- Your site renders Markdown differently (MDX, `.astro`, HTML)? Set `page_extension` and, if
  needed, change `parse_page`, `h1_of` and `first_paragraph` in `seoloop/gate.py`. Keep the tests.
- Add checks there, not in a prompt. A check in a prompt is a suggestion; a check in code is a gate.
