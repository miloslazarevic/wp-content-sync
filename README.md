# wp-content-sync

A private tool for pulling WordPress page content out of Local.app sites as
paste-ready HTML, and for driving Google-Doc-sourced content updates across many
client sites with Claude Code.

It never writes to WordPress. Pulling content out is automated (`wpsync`); routing and
merging a content update is done by Claude Code (the `wp-merge` skill) and reviewed by
you at two points; pasting the result into production is a manual step you do yourself.

See [`PLAN.md`](PLAN.md) for the full design rationale and [`build.md`](build.md) for
how it was built, including decisions made once real client data was in front of us.
This file is the day-to-day "how do I use it" reference.

## One-time setup

```
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

Everything below assumes commands run through that virtualenv
(`./.venv/bin/python3 -m wpsync ...`), or with it activated (`source .venv/bin/activate`,
then plain `python -m wpsync ...`).

## Adding a client

```
python -m wpsync init <client-name>
```

This copies `clients/_template/` to `clients/<client-name>/` (refuses to overwrite an
existing folder). Two files need filling in:

### `clients/<client-name>/profile.yml`

```yaml
name: uic
label: "UIC Business"

site:
  wp_path: "~/Local Sites/uic-business/app/public"   # contains wp-config.php

database:
  # Supply EXACTLY ONE of socket or host+port. Find both in Local.app -> select
  # the site -> Database tab. Or, on macOS, in
  # ~/Library/Application Support/Local/sites.json (match the site by name/path
  # to get its ID, then the socket is at
  # ~/Library/Application Support/Local/run/<that ID>/mysql/mysqld.sock).
  socket: "~/Library/Application Support/Local/run/<site-id>/mysql/mysqld.sock"
  # host: 127.0.0.1
  # port: 10005

dump:
  post_types: [page]
  post_status: [publish, draft]
  include: []   # page paths to limit to (no leading/trailing slash); empty = all
  exclude: []   # page paths to skip
```

Everything else about the database connection (`DB_NAME`, `DB_USER`, `DB_PASSWORD`,
table prefix) is read automatically from `wp-config.php` — don't duplicate it in the
profile unless it needs overriding.

The site must be **running in Local.app** for `list`/`dump` to connect — Local's MySQL
only listens while the site is started.

### `clients/<client-name>/CLAUDE.md`

Fill this in **after** the first `dump` (below), by looking at the actual dumped
content. It's a skeleton with prompts for each section:
- **Editor type** — Classic Editor (bare newlines / `<p>` tags in `post_content`) or
  block editor (`<!-- wp:... -->` comments)? Check a few `current/**.html` files.
- **Bootstrap / CSS framework version**, **class conventions**, **shortcodes and
  embeds**, **known quirks** — whatever a merge into this client needs to respect.
- **ACF / postmeta** — is this client ACF-heavy? (See "Known gaps" below — it usually
  is, at least partially.)

This file loads automatically whenever Claude Code touches that client's files — no
need to reference it explicitly.

## Commands

All run as `python -m wpsync <command> ...`.

| Command | What it does |
|---|---|
| `init <client>` | Scaffold a new client from the template. Won't overwrite an existing one. |
| `list <client>` | Connect and print the page inventory. Writes nothing to disk — use this to sanity-check a new profile before dumping. |
| `dump <client>` | Full dump: writes `current/**`, `pages.csv`, `summary.html`. |
| `dump --all` | Dump every client that has a `profile.yml`. Continues past a failing client and prints a pass/fail summary at the end. |
| `verify <client>` | After pasting `staged/` into production and re-running `dump`, diffs `staged/**` against the fresh `current/**`. Reports anything that failed to paste or got altered on save. |
| `lint <client>` | Advisory scan of `staged/**` for leftover Google Docs export artifacts (inline `style=`, `font-family`, Google's internal ids). Flags, never blocks. |

Every command exits non-zero on failure (`dump --all` exits non-zero if *any* client
failed). Connection and config problems fail loudly with a specific message — a
"connection refused" almost always means the site isn't running in Local.app.

## What a dump produces

- **`current/**.html`** — one file per page with real content, byte-faithful
  `post_content` (UTF-8, LF line endings, no header comments), named by full
  parent-chain path so pages that share a slug under different parents
  (`/som/admissions/` vs `/gsoe/admissions/`) never collide. Paste-ready as-is into the
  Classic Editor's Text tab.
- **`pages.csv`** — every page in scope: `id,path,file,title,status,modified`. A page
  with empty `post_content` (see "Known gaps") still gets a row here, just with a blank
  `file` column — there's no `current/<path>.html` for it.
- **`summary.html`** — open this in a browser for a readable version of the same
  inventory: page ID, path (linked to its `current/<path>.html`, when one exists), slug,
  title, status, assigned page template, an empty/has-content badge, and last-modified
  date. Any dump warnings (collisions, orphaned parents, empty-content pages) are called
  out at the top.

**None of this is committed to git** — see "What's tracked" below.

## Updating content from a Google Doc

Per round, per client, this is what actually touches page content:

1. **Refresh the baseline.** Pull production down into Local.app if needed, then
   `dump <client>`. A stale local database means every diff is computed against
   content production has already moved past — this step matters more than anything
   the tooling does.
2. **Drop the export in.** Save the Google Doc's HTML export into
   `clients/<client>/incoming/`.
3. **Ask Claude Code to map it.** In a Claude Code session working in this repo, ask it
   to run the mapping step for that client (the `wp-merge` skill). It reads `incoming/`
   and `pages.csv` and writes `clients/<client>/mapping.md`: which source section
   targets which page, which sections didn't match anything, which pages are untouched
   this round. It starts as `Status: DRAFT`.
4. **Review and approve the mapping.** This is the most important review in the whole
   workflow — a routing mistake here is far cheaper to catch now than after content is
   merged. Once it looks right, flip the file's status line to `Status: APPROVED`
   (or ask Claude to do it once you've confirmed).
5. **Ask Claude Code to merge.** It reads the approved mapping, merges each page
   (`current/<path>.html` + its mapped source section → `staged/<path>.html`), writes a
   `changes/<path>.md` report per page, and runs `wpsync lint` on the result. A page
   whose content doesn't actually change gets no `staged/` file at all.
6. **Review and paste.** Read the change reports, then paste each `staged/<path>.html`
   into that page's Classic Editor Text tab yourself — this step stays manual.
7. **Verify (recommended).** Re-run `dump <client>`, then `wpsync verify <client>`.
   Anything it flags either failed to paste or was altered by WordPress on save (e.g.
   `kses` filtering).

The merge rules themselves (preserve `wpautop` semantics, never restructure existing
markup, strip Google Docs export artifacts, change only what the source actually
changes) live in the root [`CLAUDE.md`](CLAUDE.md) and
[`.claude/skills/wp-merge/SKILL.md`](.claude/skills/wp-merge/SKILL.md) — Claude Code
picks them up automatically, nothing to invoke by name.

## Known gaps

- **ACF / page-builder content isn't covered.** Only `post_content` is dumped. A page
  built with ACF flexible-content fields (or another page builder) can have some or all
  of its real content living in `postmeta` instead — that page still shows up in
  `pages.csv`/`summary.html`, flagged as empty, but gets no `current/<path>.html` and
  can't be merged into by this tool yet. If a content round needs to touch one of these
  pages, that has to be handled by hand outside this tool for now.
- **Local database freshness is a manual precondition** the tool can't detect — see
  step 1 above. `summary.html`'s modified-date column is a hint: if nothing's changed
  in months, the local copy is probably stale.
- **Block-editor (Gutenberg) content isn't handled.** The merge rules assume Classic
  Editor bare-newline/`<p>`-tag conventions. Check a client's `CLAUDE.md` before
  merging into it.

## What's tracked in git

Only a client's `profile.yml` and `CLAUDE.md` are committed. Everything pulled or
generated — `current/`, `staged/`, `changes/`, `incoming/`, `pages.csv`,
`summary.html`, `mapping.md` — is gitignored per client: it's real client site content
and doesn't belong in a repo that syncs to GitHub, even a private one.

Commit messages follow `[Type] Short description` (e.g. `[Add] UIC profile`,
`[Fix] parent-chain path collision on duplicate slugs`). Claude Code never runs
`git commit`/`git push` on its own in this repo — it hands over a commit message and
you commit and push yourself after reviewing.

## Repo layout

```
wp-content-sync/
├── CLAUDE.md                 # merge rules + conventions that apply to every client
├── PLAN.md                   # original design doc and rationale
├── build.md                  # phased build log, including real-world findings
├── requirements.txt
├── .claude/skills/wp-merge/  # the mapping + merge procedure Claude Code follows
├── wpsync/                   # the Python runner (config, db, paths, dump, cli, ...)
└── clients/
    ├── _template/            # profile.yml + CLAUDE.md skeleton for a new client
    └── <name>/
        ├── profile.yml       # tracked
        ├── CLAUDE.md         # tracked
        ├── current/          # gitignored
        ├── pages.csv         # gitignored
        ├── summary.html      # gitignored
        ├── incoming/         # gitignored
        ├── mapping.md        # gitignored
        ├── staged/           # gitignored
        └── changes/          # gitignored
```

Adding another client is one `init` call plus filling in two files — no code changes.
