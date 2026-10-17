# Public-site content

Every public page's copy lives here as one markdown file per section, never in
page component source. A section file has YAML frontmatter followed by an
optional markdown body.

```markdown
---
id: how-it-works.five-steps
page: how-it-works
anchor: five-steps
title: Five steps
status: published
personas: [grantee, funder]   # optional
items:                        # optional, structured entries
  - title: Budget
    body: Create a structured project budget.
---
Optional prose body, rendered as markdown (no raw HTML).
```

## Required fields

- `id` — globally unique, stable, in the form `<page>.<slug>`.
- `page` — one of `home`, `how-it-works`, `security`, `about`, `contact`, `legal`.
- `anchor` — a URL fragment, unique within its page. The section's canonical
  URL is `<page route>#<anchor>`.
- `title` — the section heading as shown to visitors.
- `status` — `published` or `draft`.

## Optional fields

- `personas` — a subset of `grantee`, `funder`, `technical`.
- `items` — a list of structured entries (cards, steps, quotes, FAQs). Each
  item needs a `title` or `quote`, and a `body` or `attribution`.

## IDs and anchors are stable

Once published, a section's `id` and `anchor` don't change when only its
wording changes — downstream consumers (including the site assistant) cite
sections by both. Renaming or removing either is a breaking content change.

## Draft lifecycle

A section ships as `status: draft` when its wording isn't confirmed yet. Draft
sections never render in a production build. In development and preview
builds they render with a visible "TBC" marker so authors and reviewers can
see what's still pending. Flip `status` to `published` once the wording is
confirmed — no code change needed.
