---
name: wp-merge
description: Route a Google Doc export to the right WordPress pages (mapping) and merge it into that client's current page HTML (merge), for a wp-content-sync client. Use when the user asks to map or merge incoming content for a client, or has just dropped a new export into a client's incoming/ folder.
---

# wp-merge

Drives PLAN.md §8 steps 3–4 for one client, one round. Read the root `CLAUDE.md` (merge
rules, approval gate, round hygiene) and `clients/<name>/CLAUDE.md` (that client's
specifics) before doing anything below — both apply to every step here.

This skill never writes to WordPress and never touches `current/**` — those are the
read-only baseline from the last `dump`.

## Preconditions

Before starting, confirm:
- `clients/<name>/current/**` and `clients/<name>/pages.csv` exist and are current (the
  operator is responsible for having run `dump` recently — see PLAN.md §11 on staleness;
  if `pages.csv` looks stale, say so before proceeding).
- `clients/<name>/incoming/` has at least one new file.
- `clients/<name>/CLAUDE.md` has its "Editor type" section filled in. If it says block
  editor, or is still a placeholder, stop and flag it rather than guessing — the wpautop
  merge rules below assume Classic Editor content.

## Step 0 — Clear stale round artifacts

Before generating anything, delete any existing `clients/<name>/mapping.md`,
`clients/<name>/staged/`, and `clients/<name>/changes/`. A new round never inherits a
prior round's files (root `CLAUDE.md` → Round hygiene).

## Step 1 — Mapping

Read every file in `clients/<name>/incoming/` and `clients/<name>/pages.csv`. For each
distinct section of the source document (a section is whatever unit of content
plausibly targets one page — usually delimited by headings), decide which page path it
targets, based on heading text, page titles in `pages.csv`, and obvious topical match.

Write `clients/<name>/mapping.md`:

```
Status: DRAFT

# Mapping — <name> — <incoming file(s)>, <date>

## Routing
| Source section | Target page | Notes |
|---|---|---|
| "About Us" (incoming/export.html, heading 1) | about | |
| "Admissions — School of Music" (heading 3) | som/admissions | |

## Unmatched source sections
- "New Faculty Spotlight" — no obvious target page; needs a human decision.

## Untouched pages this round
- gsoe/admissions
- contact
```

Do not guess past what's genuinely ambiguous — list it under "Unmatched source
sections" instead of forcing a mapping. **Stop here.** Tell the user `mapping.md` is
ready for review and that merge won't run until it's approved.

## Step 2 — Wait for approval

Do not proceed to Step 3 in the same turn you wrote `mapping.md`, and never proceed
without checking: `clients/<name>/mapping.md` must start with `Status: APPROVED`
(the user edits the DRAFT line themselves, or asks you to flip it once they've reviewed
the routing table). If it still says `DRAFT`, stop and say so — do not merge.

## Step 3 — Merge

For each row in the approved routing table:

1. Read `clients/<name>/current/<path>.html` and the mapped source section.
2. Apply the merge rules from the root `CLAUDE.md` (wpautop preservation, structure
   preservation, shortcode handling, Google Docs artifact stripping) and this client's
   `CLAUDE.md` (class conventions, known quirks).
3. If the merged result is byte-identical to `current/<path>.html`, write nothing to
   `staged/` for this page.
4. Otherwise write `clients/<name>/staged/<path>.html` (the full merged page, paste-ready
   — no header comments, matching whatever line-ending/newline convention
   `current/<path>.html` uses) and `clients/<name>/changes/<path>.md`:

```
# Changes — <path>

Summary: <one line — what changed and why>

## Changes
1. Replaced the second paragraph under "Mission" with updated copy from the source's
   "About Us" section.
2. Added a sentence to the intro paragraph naming the new program.

## Flagged for review
- The source also mentions a new deadline that doesn't appear on this page anywhere —
  unclear if it belongs here or on a different page.
```

Leave the "Flagged for review" section out entirely when there's nothing to flag —
don't manufacture filler.

## Step 4 — Report

Summarize for the user: which pages got a `staged/` file, which were skipped because
nothing changed, and the total count of flagged items across all change reports (so they
know how much of the review is routine vs. needs a decision). Point them at PLAN.md §8
step 5 (paste) and step 6 (optional verify) as the next manual steps — this skill's job
ends at `staged/` and `changes/`.
