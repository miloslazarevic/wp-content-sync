# UIC Business — client conventions

## Editor type

Classic Editor, bare-newline paragraphs (not explicit `<p>` tags) — confirmed from raw
`post_content`: body copy on `admission.html` is a plain line of text following an
`<h2>`, relying on `wpautop` to wrap it at render time. No `<!-- wp:... -->` block
editor comments anywhere in the dump. Preserve bare newlines on any merge — do not
introduce `<p>` tags.

## Bootstrap / CSS framework version

Bootstrap 5 — confirmed by the `g-0` gutter utility class (Bootstrap 5 replaced
Bootstrap 4's `no-gutters` with `g-0`), alongside standard `row`/`col-md-*`/`col-lg-*`
grid classes.

## Class conventions

- Standard Bootstrap 5 grid/utility classes throughout (`row`, `col-md-6`, `mb-3`,
  `p-4`, `h-100`, `d-flex`, `align-items-center`, `g-0`).
- Custom classes layered on top, mirroring Bootstrap naming: `txt-blue` / `txt-white`
  (custom text-color utilities, not Bootstrap's own `text-*`), `bg-blue` / `bg-neutral`,
  `ranking-section`, `rank`, `red-line`, `blue-blockquote`, `anchor-link` (used on
  heading ids for in-page jump links, e.g. `id="admission-requirements"`).

## Shortcodes and embeds

Copied verbatim, never reformatted — seen across the dump:
- `[acf field="..." post_id="options"]` / `[raw_acf field="..." post_id="option"]` —
  pulls an ACF options-page field (e.g. phone number, RFI form markup) into the page.
- `[archa-form ...]`, `[archa-form-multi-step ...]`, `[archa-next-app-deadline ...]`,
  `[archa-next-start-date ...]` — third-party enrollment/CRM form embeds, with
  attributes like `program_static_slug`, `international`, `show_concentrations`.
- `[bloginfo key='template_url']` — appears **inline inside attribute values** (e.g.
  `style="background-image: url([bloginfo key='template_url']/images/...)"`), not just
  as a standalone shortcode. Preserve exactly, including its position inside the
  attribute.

## Known quirks

- Existing pages use inline `style="background-image: ...; ..."` attributes
  legitimately (for background images) — this is native to the current page, not a
  Google Docs export artifact. The "strip inline styles" merge rule only applies to
  content copied in *from* a Google Doc export; never strip a `style` attribute that
  was already on the current page.
- HTML comments are sometimes used deliberately as structural section labels
  (`<!-- Rankings Section -->`) or to intentionally keep old copy around, commented out
  (`<!--<div class="source">...</div>-->`). Leave both alone unless the source document
  says to change that specific content — they're not clutter to clean up.

## ACF / postmeta

**ACF-heavy.** Every one of the 29 pages has ACF fields; 14 of 29 have **zero**
`post_content` and are built entirely through ACF flexible-content fields (landing
pages like `mba`, `home`, `online-mba*`, plus utility pages like `thanks`, `articles`,
`index`, `about/faq`). These 14 are still listed in `pages.csv` and `summary.html`
(flagged with an "empty" badge) so they're visible in the inventory, but `dump` writes
no `current/<path>.html` for them — there's nothing in `post_content` to write — and
wpsync has no postmeta dump yet. **Any content update round that targets one of these
pages cannot be handled by this tool yet** — a page listed in `pages.csv` with a blank
`file` column means exactly this. Flag it back to the user rather than guessing at
which ACF fields to touch, and never treat a missing `current/<path>.html` as "the page
is blank, write fresh content" — the real content is in ACF fields this tool can't see.

The remaining 15 in-scope pages aren't purely classic either: most also carry a handful
of ACF fields alongside real `post_content` (hero text, CTAs, etc. — commonly under 10
fields per page, vs. 40-90+ on the ACF-only pages). Those secondary ACF fields are
**not** covered by a page's `current/<path>.html` — a content update might still miss
something if it targets one of them. When in doubt, note it as ambiguous in the change
report rather than assuming `post_content` is the whole page.
