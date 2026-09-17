# wp-content-sync — Build Plan

Phased, actionable build steps for PLAN.md's three phases (§12). Each phase ends with a
manual validation gate — do not start the next phase until the gate passes.

---

## 0. Clarifications folded in from plan review

These resolve ambiguities in PLAN.md before code is written. They don't change scope —
just remove decisions that would otherwise get made ad hoc mid-implementation.

1. **Editor-type check.** Before the first merge on any client, confirm whether its pages
   were authored in the Classic Editor (bare newlines / `<p>` tags in `post_content`) or the
   block editor (`<!-- wp:... -->` comments present). If block editor content is found,
   treat it like the ACF gap in PLAN.md §11: flag it, don't attempt the `wpautop`-preserving
   merge rules against it, and decide a plan for that client separately.
2. **`include`/`exclude` semantics.** Paths are WordPress URL paths without a leading slash
   and without trailing slash (`som/admissions`, matching the derived file path minus
   `.html`). Filtering is applied **after** parent-chain resolution, never before — a page
   can be excluded from output while still being used to resolve its children's paths.
3. **Round-scoped directories are cleared per round.** At the start of each update round
   (PLAN.md §8 step 2, when a new file lands in `incoming/`), clear `staged/`, `changes/`,
   and `mapping.md` before regenerating them. `current/` is already cleared on every dump
   (§7); this extends the same discipline to the other generated directories so a new round
   never inherits a prior round's leftovers.
4. **Deterministic collision resolution.** Before assigning parent-chain paths, sort the
   full post list by `ID` ascending. When two posts resolve to the same path, the
   lower-ID post keeps the plain path and the higher-ID post gets `-{ID}` appended. Same
   input always produces the same output.
5. **Socket/host validation.** `config.py` validates at load time (not at connection time)
   that exactly one of `database.socket` or `database.host`+`database.port` is present.
   Zero or both is a fail-loud config error naming the profile file.
6. **Mapping approval marker.** `mapping.md` starts with a status line:
   `Status: DRAFT` / `Status: APPROVED`. The merge step (§8 step 4) refuses to run against a
   mapping file that isn't `APPROVED`. This is a text convention, not enforced by anything
   beyond the merge skill checking it — matches the tool's manual-gate philosophy.

### Learned during the first real test (UIC)

Decisions made once real client data was in front of us — supersede the equivalent
guidance in PLAN.md where they conflict.

7. **Pulled/generated content is never committed.** `current/`, `staged/`, `changes/`,
   `incoming/`, `pages.csv`, `summary.html`, and `mapping.md` are gitignored per client.
   This reverses PLAN.md §10's git-audit-trail design — real client site content
   shouldn't live in a repo that syncs to GitHub, even a private one. Only `profile.yml`
   and `CLAUDE.md` are tracked per client. See `CLAUDE.md`'s Git conventions section.
8. **Empty-`post_content` pages are listed, not excluded, but get no file.** `dump`
   never writes `current/<path>.html` for a page with empty `post_content` — almost
   always ACF/flexible-content or a page builder rather than the editor (PLAN.md §11's
   ACF gap, first hit for real on UIC: 14 of 29 pages). The page still appears in
   `pages.csv` (with a blank `file` column) and `summary.html` (flagged with an "empty"
   badge) — hiding it via `dump.exclude` was tried first and rejected: it made pages
   like `about/faq` invisible in the inventory, which is worse than an empty row. `dump`
   also prints a console warning naming every affected path. `wpsync` still has no
   postmeta dump; a mapping/merge round must never target one of these pages (see the
   `wp-merge` skill's preconditions).
9. **The dump also writes `summary.html`.** A single-file, browsable report per client
   (`clients/<name>/summary.html`, gitignored like the rest) — page ID, path (linked to
   `current/<path>.html`), slug, title, status, assigned page template, and an
   empty/has-content badge, plus the same warnings `dump` prints to the console. Written
   only by `dump`, never by `list` (which still writes nothing to disk, per PLAN.md §7).

---

## Phase 1 — Dump

Goal: `init`, `list`, `dump`, `dump --all` all work end-to-end against one real client
(`cal-lutheran`). No Claude Code involvement yet — pure Python.

### 1.1 Scaffolding
- Create the repo layout from PLAN.md §2: `wpsync/` package, `clients/_template/`,
  `requirements.txt` (`pymysql`, `PyYAML`).
- `clients/_template/profile.yml` — the annotated schema from PLAN.md §3, all dump fields
  present but empty/commented.
- `clients/_template/CLAUDE.md` — empty skeleton with section headers (filled in Phase 2).

### 1.2 `config.py`
- Load and parse `profile.yml` (PyYAML).
- Parse `wp-config.php`: regex for `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `$table_prefix`,
  tolerant of both quote styles and whitespace variants (PLAN.md §3).
- Missing `$table_prefix` → default `wp_`, emit a warning.
- Validate `wp_path` exists and contains `wp-config.php`; fail loudly with the path if not.
- Validate exactly one of `socket` / `host`+`port` is set (clarification #5); fail loudly
  naming the profile file if not.
- Validate `table_prefix` against `^[A-Za-z0-9_]+$` (needed before SQL interpolation in 1.3).

### 1.3 `db.py`
- `pymysql` connection: `unix_socket` when profile supplies a socket, else `host`+`port`.
  Always `charset="utf8mb4"`.
- Catch connection-refused and raise a specific error: "site is not running in Local.app —
  start it and try again" instead of a raw driver traceback.
- Page query per PLAN.md §4, parameterized `IN` lists for `post_type`/`post_status`; prefix
  interpolated only after the regex validation in 1.2.
- Returns raw rows: `id, post_parent, post_name, post_title, post_status, post_modified,
  post_content`.

### 1.4 `paths.py`
- Sort rows by `ID` ascending (clarification #4).
- Build `id → post` map, walk `post_parent` to root for each post to derive the full path.
- Edge cases, each producing a warning (collected, not printed inline — see 1.6):
  - Orphaned parent (missing/non-page ancestor) → treat as root level.
  - Parent cycle → cap walk depth (e.g. 50), treat as root level.
  - Empty `post_name` → `untitled-{ID}`.
  - Path collision after the walk → lower ID keeps the path, higher ID gets `-{ID}`.
- Returns `path → post` plus a list of warnings.

### 1.5 `dump.py`
- Apply `include`/`exclude` from the profile against resolved paths (clarification #2:
  post-resolution, normalized `no-leading/no-trailing-slash` form).
- Clear `current/` entirely before writing (PLAN.md §7).
- Write `current/<path>.html`: byte-faithful `post_content`, UTF-8, LF, no added trailing
  newline, no header/comment injected.
- Write `pages.csv`: `id,path,file,title,status,modified`, one row per page written (post
  include/exclude filtering, so it matches what's actually on disk).

### 1.6 `cli.py`
- `init <client>`: copy `clients/_template/` → `clients/<client>/`, refuse to overwrite an
  existing folder.
- `list <client>`: connect, resolve paths (1.3+1.4), print inventory + any warnings, write
  nothing to disk.
- `dump <client>`: full pipeline (1.3→1.4→1.5), print a summary (page count, warning count).
- `dump --all`: iterate every folder under `clients/` with a `profile.yml`, continue past
  per-client failures, print a final success/failure table, exit non-zero if any failed.
- Every warning from 1.4/1.5 surfaces in the command's stdout summary, not just logs.

### 1.7 First real client
- `init cal-lutheran`, fill in `profile.yml` (socket path + `wp_path` from Local.app's
  Database tab), leave `dump` scope as defaults.

### Phase 1 validation gate
- `list cal-lutheran` output matches the page tree visible in WP admin (spot-check parent/
  child relationships, especially any known duplicate-slug pages).
- `dump cal-lutheran` succeeds; spot-check 3–4 `current/**.html` files against
  "View Page Source" / DB values for byte-fidelity (curly quotes, em dashes intact).
- Confirm `pages.csv` matches the file tree written.
- Re-run `dump` a second time with no DB changes — output must be byte-identical (checks
  determinism from clarification #4 and confirms no incidental reformatting).
- `git status` shows only `clients/cal-lutheran/profile.yml` and `CLAUDE.md` as
  trackable — confirm `current/`, `pages.csv`, and `summary.html` are gitignored and
  never staged (clarification #7: pulled content is never committed).

**Do not write any other client's profile until this gate passes** (PLAN.md §12).

---

## Phase 2 — Claude Code configuration

Goal: the mapping → merge workflow (PLAN.md §8 steps 3–4) works end-to-end on
`cal-lutheran` with a real Google Doc export. No new Python code.

### 2.1 Root `CLAUDE.md`
- Merge rules in full from PLAN.md §9 (wpautop preservation, structure preservation,
  shortcode handling, Google Docs artifact stripping, change discipline).
- The never-write-to-WordPress constraint, stated explicitly and unambiguously.
- Repo conventions: commit message format (`[Type] Short description`), what gets committed
  and when.

### 2.2 `clients/_template/CLAUDE.md`
- Placeholder sections: Bootstrap version, class conventions, recurring markup patterns,
  shortcodes/embeds that must survive a merge untouched, known quirks.

### 2.3 `clients/cal-lutheran/CLAUDE.md`
- Fill in real specifics by inspecting the actual dumped `current/**.html` files: Bootstrap
  version, real class names in use, any shortcodes/embeds found, quirks noticed while
  reading the dumps.
- **Editor-type check (clarification #1):** inspect a handful of `current/**.html` files
  for `<!-- wp:...` block comments. If present, note it here as a known gap before doing any
  merge work for this client.

### 2.4 `.claude/skills/wp-merge/SKILL.md`
- The mapping procedure (§8 step 3): read `incoming/` + `pages.csv`, produce `mapping.md`
  with three sections — section→page routing, unmatched source sections, untouched pages.
  `mapping.md` starts with `Status: DRAFT` (clarification #6).
- The merge procedure (§8 step 4): refuse to proceed unless `mapping.md` starts with
  `Status: APPROVED` (clarification #6). Per page: `current/<path>.html` + mapped source
  section → `staged/<path>.html` + `changes/<path>.md`.
- Change report format from PLAN.md §9: one-line summary, ordered list of concrete changes,
  flagged section for ambiguous cases.
- Explicit instruction: a page with no actual content change is not written to `staged/`.
- Explicit instruction: before generating `mapping.md` or `staged/`, clear any existing
  `mapping.md`/`staged/`/`changes/` from a prior round (clarification #3).

### 2.5 Dry run
- Get (or construct from a fixture) one real Google Doc HTML export touching 2–3
  `cal-lutheran` pages, drop it in `incoming/`.
- Run the mapping stage, review `mapping.md` by hand, flip it to `Status: APPROVED`.
- Run the merge stage, review `staged/**.html` and `changes/**.md` by hand against §9 rules:
  bare newlines vs `<p>` tags preserved correctly, no Google Docs artifacts left over,
  shortcodes untouched, unrelated markup untouched.

### Phase 2 validation gate
- At least one full round (mapping → approval → merge) produced a `staged/` file a human
  would be comfortable pasting into production with no further edits.
- The change report for that page accurately describes every change made — no silent
  changes, nothing missing.

---

## Phase 3 — Verify

Goal: a cheap post-paste check that catches paste failures/`kses` mangling before anyone
finds them by loading the live page.

### 3.1 Verify step
- Simplest form, matching PLAN.md §8 step 6: after pasting `staged/` into production,
  re-run `dump <client>`, then `diff -r clients/<client>/staged clients/<client>/current`
  for the pages that were pasted this round.
- If a lightweight ergonomic win is wanted, add `wpsync verify <client>`: diffs `current/`
  against `staged/` for every file present in `staged/`, prints mismatches, exits non-zero
  if any differ. Optional — the manual `diff -r` already satisfies PLAN.md; only add the
  command if it removes real friction.

### 3.2 (Optional stretch) Pre-merge lint
- Not in PLAN.md, but cheap and catches rule violations before human review costs time: a
  small check over `staged/**.html` for leftover Google Docs artifacts (`style=`,
  `font-family`, `<span>` with only a `style`/`class` attribute Google generates, `id`
  attributes matching Google's `docs-internal-guid-*` pattern). Flag, don't block — the
  human review in §8 step 5 is still the real gate.

### Phase 3 validation gate
- Run the verify step after a real paste; confirm it correctly flags a deliberately
  introduced mismatch (e.g. manually edit one pasted page slightly differently than staged)
  and reports clean when everything matches.

---

## Rollout (after all three phases are in daily use on `cal-lutheran`)

- Repeat 1.7 + 2.3 for each remaining client: `init`, fill `profile.yml`, `list` to validate
  before first `dump`, fill in that client's `CLAUDE.md` from its actual dumped content,
  including the editor-type check (clarification #1) and a check for ACF-heavy content
  (PLAN.md §11) before assuming the editor-content-only scope covers that client.
- No code changes expected during rollout — if one is needed, it means Phase 1 missed an
  edge case; fix it there, not per-client.
