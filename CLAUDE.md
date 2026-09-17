# wp-content-sync

Rules that apply to every client. `clients/<name>/CLAUDE.md` holds that client's
specifics and loads automatically alongside this file when a client's files are
touched — no invocation needed, no ambiguity between clients.

## Non-negotiable constraint

**Never write to WordPress.** Every database this tool touches is read-only. Pasting
into production is a manual step the human operator performs with the existing Classic
Editor workflow — never automate, script, or suggest automating that step. No REST API,
no SSH, no WP-CLI.

## The update workflow

Per round, per client: refresh the baseline (`dump`) → drop the Google Doc export in
`incoming/` → **mapping** → human approval → **merge** → human paste → optional verify.
See PLAN.md §8 for the full narrative and `.claude/skills/wp-merge/SKILL.md` for the
mapping/merge procedure itself.

### Round hygiene

At the start of a new round (a new file lands in `incoming/`), clear any existing
`mapping.md`, `staged/`, and `changes/` before regenerating them. A round never inherits
a prior round's leftovers.

### The approval gate

`mapping.md` starts with a `Status: DRAFT` line. **Never run the merge step against a
mapping file that isn't `Status: APPROVED`.** Mapping is the routing decision — which
source section lands on which page — and it must be reviewed by a human before any page
content is touched. This is the single most important gate in the whole workflow: one
source document feeding many pages means a routing mistake is invisible until it's
already merged.

## Merge rules

These apply to every merge, for every client.

**Preserve `wpautop` semantics.** Classic Editor content typed in Visual mode stores
paragraphs as bare newlines, not `<p>` tags — WordPress applies `wpautop` at render time.
Match whatever the existing page already does. If a page uses bare newlines, keep bare
newlines. If it uses explicit `<p>` tags, use explicit tags. **Never convert between the
two as part of a content update** — it silently changes the rendered spacing.

**Preserve structure and semantics.**
- Keep the existing page's markup structure, class names, and heading hierarchy. The
  source document supplies copy, not structure.
- Shortcodes (`[...]`) are copied verbatim — never reformatted, never reordered, never
  moved across a paragraph boundary.
- Anything on the current page with no counterpart in the source document stays
  untouched.
- Strip Google Docs export artifacts from incoming content before merging: inline
  `style` attributes, `<span>` wrappers carrying only styling, Google-generated `id`
  attributes, `font-family` declarations. Map the result onto the client's existing
  classes (see that client's `CLAUDE.md`).

**Change discipline.**
- Change only what the source document actually changes. No opportunistic cleanup, no
  accessibility fixes, no class renaming — raise those in the change report as prose
  instead of applying them silently.
- A page whose content doesn't change is not written to `staged/` at all.

**Editor-type check.** Before merging into a client for the first time, confirm in that
client's `CLAUDE.md` whether its pages use the Classic Editor (bare newlines / `<p>`
tags) or the block editor (`<!-- wp:... -->` comments in `post_content`). The wpautop
rule above only applies to Classic Editor content — if a client turns out to use the
block editor, stop and flag it rather than applying these rules blindly.

**ACF gap.** `current/**.html` only ever contains `post_content`. If a client is
ACF-heavy, some or all of what a Google Doc update targets may live in `postmeta`
instead and won't appear here at all — see PLAN.md §11 and that client's `CLAUDE.md`.

### Change report format (`changes/<path>.md`)

Per page: a one-line summary, an ordered list of concrete changes (what was replaced,
added, removed, and where), then a flagged section for anything ambiguous — content that
could map to more than one location, source sections that didn't fit cleanly, or
existing content the source contradicts.

## Git conventions

- Commit messages: `[Type] Short description` — e.g. `[Add] UIC profile`,
  `[Fix] parent-chain path collision on duplicate slugs`.
- **Never commit pulled or generated WordPress content.** `current/`, `staged/`,
  `changes/`, `incoming/`, `pages.csv`, `summary.html`, and `mapping.md` are gitignored
  per client (see `.gitignore`) — it's real client site content and doesn't belong in a
  repo that syncs to GitHub. Only a client's `profile.yml` and `CLAUDE.md` (config and
  conventions, no site content) are tracked.
  - This reverses PLAN.md §10's original design, which committed `current/` as a git
    audit trail. That trade-off was accepted deliberately during the first real test
    (UIC) — content privacy wins over the audit trail. There is currently no audit
    trail across dumps; if that's ever needed again, it'll need a different mechanism
    than committing raw content (e.g. a local-only history, not one that syncs to
    GitHub).
- **Never run `git commit` or `git push`, and never add commit co-authorship, on the
  user's behalf.** Hand over a ready-to-use commit message and let the user commit and
  push themselves — they review every change before it goes to GitHub.
