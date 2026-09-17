# wp-content-sync — Implementation Plan

A private, single-repo tool for pulling WordPress page content out of Local.app sites as
paste-ready HTML, and for driving Google-Doc-sourced content updates across many client
sites with Claude Code.

---

## 1. Purpose

Today the process is: convert a Google Doc to HTML by hand, clean it up by hand, then
hand-merge it into WordPress pages through the Classic Editor. This repo automates the two
mechanical halves of that — getting current page content out of WordPress, and producing a
reviewed set of merged, paste-ready files — while leaving the actual paste into production
as a manual step performed with the existing workflow.

### Scope

- Pull page content from a Local.app site's MySQL database into per-page HTML files.
- Hold per-client markup conventions so merges respect each site's existing structure.
- Produce, per update round, a set of merged `staged/` files and a human-readable change
  list.

### Non-goals

Explicitly out of scope. Do not implement these, and do not add them speculatively.

- **No writes to WordPress.** The tool is read-only against every database. Pasting into
  prod is manual and stays manual.
- **No REST API, no SSH, no WP-CLI.** The only data source is the Local.app MySQL database.
- **No ACF / postmeta.** Editor content (`post_content`) only, for now. See §11.
- **No changes to client repositories.** Nothing this repo produces is ever committed to a
  client's codebase. This repo is private and standalone.
- **No Local.app auto-discovery.** Profiles are written by hand once per client. Scanning
  Local's internal config to auto-generate them depends on undocumented layout that breaks
  on Local updates, and hand-filling ~20 profiles is a one-time 20-minute job.

---

## 2. Repo layout

```
wp-content-sync/
├── CLAUDE.md                        # global merge rules (all clients)
├── plan.md                          # this file
├── requirements.txt
├── .claude/
│   └── skills/
│       └── wp-merge/
│           └── SKILL.md             # the merge procedure, one copy for all clients
├── wpsync/                          # the Python runner
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py                    # profile loading + wp-config.php parsing
│   ├── db.py                        # MySQL connection + page query
│   ├── paths.py                     # parent-chain path derivation, filename rules
│   └── dump.py                      # file + CSV writing
└── clients/
    ├── _template/
    │   ├── profile.yml
    │   └── CLAUDE.md
    └── cal-lutheran/
        ├── profile.yml              # connection + dump scope
        ├── CLAUDE.md                # this client's markup conventions
        ├── pages.csv                # generated: page inventory
        ├── current/                 # generated: live page content, byte-faithful
        ├── incoming/                # manual: Google Doc export(s)
        ├── mapping.md               # generated, human-approved: doc section → page
        ├── staged/                  # generated: merged, paste-ready
        └── changes/                 # generated: per-page change reports
```

Adding client #21 is one folder plus one profile. No code change.

---

## 3. Profile schema (`clients/<name>/profile.yml`)

```yaml
name: cal-lutheran
label: "Cal Lutheran"

site:
  # Path to the Local.app site's WordPress root (contains wp-config.php).
  wp_path: "~/Local Sites/cal-lutheran/app/public"

database:
  # Supply EXACTLY ONE of socket or host+port.
  # Find both in Local.app → select site → Database tab.
  socket: "~/Library/Application Support/Local/run/AbC123/mysql/mysqld.sock"
  # host: 127.0.0.1
  # port: 10005

  # Optional overrides. Normally omitted — the runner reads these from wp-config.php.
  # name: local
  # user: root
  # password: root
  # table_prefix: wp_

dump:
  post_types: [page]
  post_status: [publish, draft]
  include: []        # list of page paths; empty = all
  exclude: []        # list of page paths to skip
```

### Why the connection is split this way

`wp-config.php` is the source of truth for `DB_NAME`, `DB_USER`, `DB_PASSWORD` and
`$table_prefix` — the runner parses them out so they are never duplicated in the profile and
never drift. The one thing it *cannot* supply is the connection endpoint: Local's
`wp-config.php` says `localhost`, which resolves to a socket path Local assigns per site and
does not record in the config file. So socket-or-port is the only connection detail a human
fills in.

### wp-config.php parsing

Regex-extract the four values. Handle both `define('DB_NAME', 'local');` and
`define( "DB_NAME", "local" );` spacing/quoting variants. If `$table_prefix` is absent,
default to `wp_` but emit a warning — a custom prefix that fails to parse will produce a
confusing "table doesn't exist" error otherwise.

Fail loudly with an actionable message if `wp_path` doesn't exist or has no `wp-config.php`.

---

## 4. Database access

Library: `pymysql`.

**Connection must set `charset="utf8mb4"`.** WordPress content is utf8mb4; connecting
without it mangles curly quotes, em dashes, and accented characters into mojibake that then
gets pasted into production. This is not optional.

Prefer `unix_socket` when the profile supplies a socket, otherwise `host` + `port`.

If the connection is refused, the most likely cause by far is that the site is not running
in Local.app — MySQL only listens while the site is started. Detect connection refusal and
say exactly that, rather than surfacing a raw driver traceback.

### Query

```sql
SELECT ID, post_parent, post_name, post_title, post_status, post_modified, post_content
FROM {prefix}posts
WHERE post_type IN ({post_types})
  AND post_status IN ({post_status})
```

Filtering on `post_type` inherently excludes revisions and autosaves. Do not filter in
Python what SQL can filter, but do build the parent-chain paths in Python (§5) — that needs
the full result set in memory anyway.

Parameterize the `IN` lists properly. The table prefix is interpolated (it cannot be a bound
parameter) — validate it against `^[A-Za-z0-9_]+$` before interpolation.

---

## 5. File naming — parent-chain paths

**Do not name files by bare slug.** Child pages under different parents routinely share a
slug: `/som/admissions/` and `/gsoe/admissions/` are both `post_name = "admissions"`. Bare
slug naming silently overwrites one with the other, and the failure is invisible until
merged content lands on the wrong page.

Derive the full path by walking `post_parent` to the root, then mirror it as directories:

| Page | File |
|---|---|
| `/about/` | `current/about.html` |
| `/som/admissions/` | `current/som/admissions.html` |
| `/som/` | `current/som.html` |

A page that both has content and has children produces `som.html` *and* a `som/` directory
alongside it. That is fine and intended.

Edge cases to handle explicitly:

- **Orphaned parent** (`post_parent` points at a missing or non-page post): treat as root
  level, warn.
- **Parent cycle** (malformed data): cap the walk depth, warn, treat as root level.
- **Empty `post_name`** (drafts often have none): fall back to `untitled-{ID}`.
- **Post-walk collision** (two pages resolve to the same path): append `-{ID}` to the later
  one and warn. Never silently overwrite.

---

## 6. Output files

### `current/**.html`

**Byte-faithful `post_content`.** No prettifying, no reformatting, no tag balancing, no
re-indentation. These files are the baseline every diff is measured against and the
reference for what production actually contains. Any transformation here corrupts that.

UTF-8, LF line endings, no trailing newline added.

**No header comments inside these files.** They must stay paste-ready — the whole file
selects and pastes into the Classic Editor Text tab with nothing to strip first. All
metadata lives in `pages.csv`.

### `pages.csv`

Written per client at each dump. Columns:

```
id,path,file,title,status,modified
```

This is what Claude Code reads for page context and what the mapping stage (§8) resolves doc
sections against.

---

## 7. Commands

Entry point: `python -m wpsync <command>`.

| Command | Behavior |
|---|---|
| `init <client>` | Copy `clients/_template/` to `clients/<client>/`. Does not overwrite an existing folder. |
| `list <client>` | Connect and print the page inventory. Writes nothing. Use to verify a new profile before dumping. |
| `dump <client>` | Full dump: writes `current/**` and `pages.csv`. |
| `dump --all` | Dump every client with a profile. Continue past failures; summarize which succeeded and which failed at the end. |

Exit non-zero on failure. `dump --all` exits non-zero if any client failed.

`dump` overwrites `current/` wholesale. Stale files from pages deleted or renamed in
WordPress must not linger — clear the directory first, since git preserves the previous
state anyway (§10).

---

## 8. The update workflow

Per round of Google Doc updates, for one client:

**Step 1 — Refresh the baseline.** Pull production down into Local.app, then `dump <client>`.
If Local's database is stale, every diff is computed against the wrong baseline and the
merge will reintroduce content production has already moved past. This is the single most
likely way to get a wrong result, and it is entirely upstream of the tooling.

**Step 2 — Drop in the source.** Save the Google Doc HTML export to `incoming/`.

**Step 3 — Mapping (routing).** Claude Code reads `incoming/` plus `pages.csv` and writes
`mapping.md`: which section of the source document targets which page path, which source
sections matched nothing, and which pages are untouched this round.

**This stage exists to be reviewed by a human before anything is merged.** One source
document feeding many pages means routing is where content lands on the wrong page, and a
routing error is far cheaper to catch in a short mapping file than in a set of merged HTML
files. Do not collapse mapping and merging into one step.

**Step 4 — Merge.** Once `mapping.md` is approved, Claude Code merges per page:
`current/<path>.html` + the mapped source section → `staged/<path>.html`, plus
`changes/<path>.md`.

**Step 5 — Paste.** Review the change reports, paste `staged/` files into production using
the existing workflow.

**Step 6 — Verify (optional, recommended).** After pasting, re-run `dump` and diff the fresh
`current/` against `staged/`. Anything that differs either failed to paste or was altered on
save — for example by `kses` filtering. Cheap to run, and it catches paste errors that are
otherwise invisible until someone loads the page.

---

## 9. Merge rules

These belong in the root `CLAUDE.md` and in `.claude/skills/wp-merge/SKILL.md`. Listed here
because they are design decisions, not style preferences.

### Preserve `wpautop` semantics

This is the rule most likely to cause silent breakage. Classic Editor content typed in
Visual mode stores paragraphs as **bare newlines**, not `<p>` tags — WordPress applies
`wpautop` at render time to convert them. If a merge "cleans up" bare newlines into explicit
`<p>` tags, the rendered output changes: spacing shifts, and in some cases WordPress wraps
the explicit tags again.

Therefore: match whatever the existing page already does. If a page uses bare newlines, keep
bare newlines. If it uses explicit `<p>` tags, use explicit tags. Never convert between the
two conventions as part of a content update.

### Preserve structure and semantics

- Keep the existing page's markup structure, class names, and heading hierarchy. The source
  document supplies **copy**, not structure.
- Shortcodes (`[...]`) are copied verbatim. Never reformat them, never change their
  attribute order, never move them across a paragraph boundary.
- Anything in the current page that has no counterpart in the source document stays
  untouched.
- Strip Google Docs export artifacts from incoming content: inline `style` attributes,
  `<span>` wrappers carrying only styling, `id` attributes Google generates, and
  `font-family` declarations. Map the result onto the client's existing classes.

### Change discipline

- Change only what the source document actually changes. No opportunistic cleanup of
  unrelated markup, no accessibility fixes, no class renaming — those get raised in the
  change report as prose instead, not applied silently.
- A file whose content does not change should not be written to `staged/` at all. Empty
  diffs waste review time.

### Change report format (`changes/<path>.md`)

Per page: a one-line summary, then an ordered list of concrete changes (what was replaced,
added, removed, and where), then a flagged section for anything ambiguous — content that
could map to more than one location, source sections that didn't fit cleanly, or existing
content the source contradicts.

---

## 10. Claude Code configuration

### CLAUDE.md layering

- **Root `CLAUDE.md`** — rules that apply to every client: §9 in full, plus the repo's
  conventions and the never-write-to-WordPress constraint.
- **`clients/<name>/CLAUDE.md`** — that client's specifics: Bootstrap version (v5 for most,
  v4/v3 on older projects), class conventions, recurring markup patterns, shortcodes and
  embeds that must be preserved, known quirks.

Nested `CLAUDE.md` files load automatically when Claude Code touches files in that
directory, so working on a client's files picks up that client's conventions with no
invocation and no ambiguity between clients.

### Why not one skill per client

Skills are selected by description matching. Twenty skills with near-identical descriptions
("merge content for client X") create selection ambiguity and will occasionally pick the
wrong one. One shared procedure skill plus per-folder `CLAUDE.md` for the specifics has no
such failure mode.

### Git conventions

Commit messages: `[Type] Short description` — e.g. `[Add] Cal Lutheran profile`,
`[Fix] parent-chain path collision on duplicate slugs`.

~~**Commit `current/` after every dump.** This is the quietly valuable part: each dump
becomes a diff against the previous one, giving a running audit trail of what actually
changed in production between rounds, across every client, without touching client
repositories.~~

**Superseded during the first real test (UIC).** Pulled/generated content
(`current/`, `staged/`, `changes/`, `incoming/`, `pages.csv`, `summary.html`,
`mapping.md`) is gitignored per client and never committed — it's real client site
content and doesn't belong in a repo that syncs to GitHub, even a private one. Only
`profile.yml` and `CLAUDE.md` are tracked per client. This drops the git-audit-trail
benefit described above with no replacement yet; see `CLAUDE.md`'s Git conventions
section for the current rule.

Profiles contain Local.app database credentials, which are `root`/`root` on a local-only
socket and carry no real exposure. The repo stays private regardless.

---

## 11. Known gaps

**ACF content is not covered.** ACF field values live in `postmeta`, not `post_content`. On
ACF-heavy sites, some or all of what a Google Doc updates may not appear in these dumps at
all. Before rolling this out past the first client, check one ACF-heavy site and confirm
whether the content being updated actually lives in the editor. If it doesn't, that client
needs a postmeta dump alongside the page dump, driven by a per-client list of which fields
matter — deliberately deferred until there's a concrete case.

**Local database freshness is a manual precondition** (§8, step 1) and the tool cannot
detect it. Consider having `dump` print each page's `post_modified` alongside the dump
summary — an inventory where nothing has changed in months is a hint the local copy is
stale.

---

## 12. Build order

Each phase is independently useful. Do not start a phase before the previous one works.

**Phase 1 — Dump.** Profile loading, `wp-config.php` parsing, database connection, the page
query, parent-chain paths, `current/**` and `pages.csv`. Commands: `init`, `list`, `dump`.
On its own this replaces the manual pull, which is the bulk of the current tedium.

**Phase 2 — Claude Code configuration.** Root and template `CLAUDE.md`, the `wp-merge`
skill, the mapping and merge workflow. No code — conventions and prompts only.

**Phase 3 — Verify.** The post-paste diff of a fresh `current/` against `staged/` (§8, step
6). Small, optional, worth doing once phases 1 and 2 are in daily use.

Validate Phase 1 against a single real client before writing any profile beyond the first.