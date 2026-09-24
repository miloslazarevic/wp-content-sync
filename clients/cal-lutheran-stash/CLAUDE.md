# Cal Lutheran — client conventions

## Editor type

Classic Editor, **explicit `<p>` tags** — not bare newlines. Confirmed across multiple
pages (`about.html`, `faculty.html`, `contact-us.html`): every paragraph is wrapped in
`<p>`, often with a class (`<p class="intro">`, `<p class="fw-bold h4 mb-3 txt-purple">`).
This is the opposite convention from UIC (which uses bare newlines) — a real example of
why the merge rule says "match whatever the existing page already does" rather than
assuming one convention repo-wide. **Never convert these to bare newlines on a merge.**
No `<!-- wp:... -->` block editor comments found anywhere in the dump.

## Bootstrap / CSS framework version

Bootstrap 5 — confirmed by `data-bs-toggle`/`data-bs-target` (Bootstrap 4 used
`data-toggle`/`data-target` without the `bs-` prefix), plus `g-0`/`g-3` gutter
utilities and `gap-3`.

## Class conventions

- Standard Bootstrap 5 grid/utility classes (`row`, `col-12`, `row-cols-2
  row-cols-lg-5`, `g-3`, `d-flex`, `flex-column flex-lg-row`, `text-center`,
  `text-uppercase`).
- Custom classes layered on top: `txt-purple` / `txt-blue` / `txt-bold` (custom
  color/weight utilities, used *alongside* Bootstrap's own `fw-bold` — both appear on
  the same elements), `bg-neutral`, `gray-hr` / `blue-hr` (custom `<hr>` variants),
  `item-fact` (stat/fact tile), `custom-accordion`, `anchor-link` — used as an empty
  marker div with an `id` for in-page jump links (`<div class="anchor-link"
  id="veteran-resources"></div>`), not always on the heading itself.
- Bootstrap 5 accordion pattern in use (`accordion accordion-flush`,
  `data-bs-toggle="collapse"`) — keep `id`/`data-bs-target` pairs in sync if either
  ever needs to change, though normal content updates shouldn't touch them at all.

## Shortcodes and embeds

A much larger shortcode ecosystem than UIC's — copy all of these verbatim, exact
attributes and quoting, never reordered or reformatted:
- `[acf field="..." post_id="..."]` — ACF field pull, same family as UIC.
- `[archa-form ...]`, `[archa-form-multi-step]`, `[archa-next-app-deadline
  school_abbr="..." program_static_slug="..."]`, `[archa-next-start-date ...]` —
  third-party enrollment/CRM embeds (same vendor as UIC's `archa-*` shortcodes).
- `[bloginfo key='...']` — appears **inline inside attribute values** (e.g. an `<img
  src="[bloginfo key='url']/wp-content/uploads/...">`), same as UIC.
  - **Inconsistent quoting exists in production**: both `[bloginfo
    key='template_url']` (quoted) and `[bloginfo key=template_url]` (unquoted) appear.
    Preserve whichever form is already on the page being merged — do not "fix" the
    quoting to be consistent, that's exactly the kind of opportunistic cleanup the
    change-discipline rule forbids.
- `[home_url]` — the token for **every** internal link on this site. See the link rules
  below; this one is not optional.
- `[degree_options layout="tiles" program_type="..." school="..." filters="false"
  show_heading="false"]` — program listing widget.
- `[pullpost-content pagename="..."]` — pulls another page's content by slug (seen
  referencing PPC landing pages like `mba`, `mppa`, `msc`).
- `[text-blocks id="..." plain="1"]` — shared text snippet by id (phone numbers, form
  intros, deadline copy) — reused across many pages, edit the source snippet's page,
  not each occurrence.
- `[lightcast_widget]`, `[media-id='...']`, `[i]` — embeds/icons, preserve as-is.

## Link rules (non-negotiable)

This site is served through a **reverse proxy**: the WordPress install lives at
`https://www.callutheran.edu/programs/`. That proxy is the entire reason the
`[home_url]` shortcode exists.

1. **Every link to a page on this site uses `[home_url]/…`** — never a root-relative
   `/programs/…` path and never a hardcoded `https://www.callutheran.edu/programs/…`
   URL. Both of those break or bypass the proxy setup.
   - `href="/programs/school-for-professional-and-continuing-studies/faq/"` → **wrong**
   - `href="[home_url]/school-for-professional-and-continuing-studies/faq/"` → **right**
   - Root-relative `/programs/` links do still exist in older live content. They are
     legacy, not a convention to preserve — convert them whenever you touch a page.
2. **Every outbound link opens in a new tab**: `target="_blank" rel="noopener"`. This
   includes `https://www.callutheran.edu/…` URLs that sit *outside* `/programs/` (the
   main university site, veterans pages, financial aid pages, IDEAS, etc.) — anything
   that leaves this WordPress install counts as outbound, same domain or not.
3. Corollary: `[home_url]` links and on-page anchors (`#curriculum`) never get
   `target="_blank"`. `mailto:` links don't either.

## Known quirks

- Curly quotes, apostrophes, and en/em dashes are used throughout body copy (e.g.
  "Bachelor's Degrees for Professionals", "→" arrows in CTA links) — byte-fidelity via
  `utf8mb4` matters here more than on a plainer-copy site; double check these render
  correctly after any merge.
- `content-style-guide` exists here too (like UIC) — a real reference page for this
  client's own conventions, worth checking before assuming a pattern from this file.
- Several near-duplicate pages exist for PPC (pay-per-click) landing pages (`mba`,
  `mba-b`, `mba-c`, `mba-d`, `online-mba`, `online-mba-b`, etc.) — confirm which
  specific variant a content update is actually meant to target before merging;
  routing a change to the wrong `-b`/`-c`/`-d` variant is an easy mistake with this
  naming pattern.

## ACF / postmeta

**ACF-heavy, same pattern as UIC.** 15 of 135 pages have empty `post_content` and are
built entirely through ACF/flexible-content fields: `all-som`, `appointment`,
`articles`, `california-lutheran-university`, `request-info`, `welcome-back-som`, and
several FAQ pages under `graduate/*/faq` and
`school-for-professional-and-continuing-studies/faq`. These are listed in `pages.csv`
and `summary.html` (flagged as empty) with a blank `file` column — no
`current/<path>.html` exists for them. Per the root `CLAUDE.md`'s ACF gap section:
never treat a missing baseline as "page is blank, write fresh content" — flag it back
to the user instead. Notably **most FAQ pages across this site are ACF-only** (the
`graduate/mba/faq`, `graduate/mppa/faq`, etc. pattern) — if a content round targets
"the FAQ page" for any program, check `pages.csv` first; it's very likely one of these.
