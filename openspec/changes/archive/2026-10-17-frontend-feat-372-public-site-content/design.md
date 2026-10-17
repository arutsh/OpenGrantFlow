# Design

## Context

- `frontend-typescript/src/pages/LandingPage.tsx` renders one scrolling page. Its copy lives in JSX and in module-level constants (`SECTOR_QUOTES`, `WORKFLOW_STEPS`, `NAV_LINKS`). Nav links are `#anchor` hrefs, and the nav is `hidden sm:flex`, so mobile visitors get no links at all.
- `App.tsx` registers `/` and `/legal` as public routes, and a `*` catch-all redirects to `/dashboard`. `LandingPage` redirects authenticated users to `/dashboard` itself.
- The frontend is deployed two ways, and both treat `frontend-typescript/` as the root:
  - Vercel: `vercel.json` rewrites every path to `index.html`.
  - Docker: the `Dockerfile` does `COPY . .` inside `frontend-typescript/`, and `nginx.frontend.conf` uses `try_files`.
- The ai service image is built with context `.` (the repo root) in `docker-compose.prod.yml`, so it can read files anywhere in the repo.
- The contact form posts to web3forms directly from the browser.
- The source of truth for copy is the redesign draft (five pages, with TBC-tagged items). See proposal.md.

## Goals / Non-Goals

**Goals:**
- Content files are the only place copy lives. Their format is simple enough to parse from both TypeScript and Python.
- Section-level granularity, so a section can later be one retrieval chunk with its own citation URL.
- No new build step, Vite plugin or backend.

**Non-Goals:**
- A CMS, or content editing outside git.
- Server-side rendering or prerendering for SEO. Worth revisiting later; it does not affect the content contract.
- The assistant UI or any AI behaviour.

## Decisions

### D1. Content lives in `frontend-typescript/src/content/site/<page>/<slug>.md`
Keeping it inside the frontend root means both the Vercel and Docker frontend builds see it with no configuration change. The ai service reaches it through its repo-root build context (`COPY frontend-typescript/src/content/site ...`), which is what `ai-feat-site-assistant-retrieval-evals` will do.
- *Alternative, repo-root `content/site/`:* conceptually cleaner, since two consumers share it. Rejected because Vercel's root-directory setting would have to allow files outside the root, and the Docker frontend build context would have to widen to the repo root. That is a deploy change for no user-visible gain.

### D2. One file per section, not one file per page
A section is the smallest thing that has its own heading, URL fragment and citation. One file per section means:
- frontmatter maps 1:1 to provenance metadata;
- `git log` on a file is that section's history;
- the downstream chunker can start with "one section = one chunk" as its baseline.
- *Alternative, one file per page with heading-delimited sections:* fewer files, but IDs and anchors would come from parsing headings, which is fragile, and structured items would need a second syntax.

### D3. Frontmatter for structure, markdown body for prose
Card grids, the five steps, quotes and FAQs go in a frontmatter `items` list, and prose goes in the body. Page components pick the layout.
- *Alternative, a generic page renderer driven by a `layout` field:* rejected. The redesign's layouts vary a lot, and a layout DSL would be a second design system to maintain.

### D4. Loader: `import.meta.glob` + a `yaml` frontmatter split, validated at load
`src/lib/siteContent.ts`:
- eagerly globs `?raw` markdown;
- splits on the leading `---` fence and parses it with `yaml`;
- checks the contract (required fields, allowed `page`/`personas`/`status` values, unique `id`, unique `anchor` per page);
- exposes `getSection(id)`, which throws on an unknown ID.
The corpus is a few KB, so eager bundling costs nothing. Because validation throws at import, dev, tests and CI all fail on the first violation. `gray-matter` is avoided because it depends on Node `Buffer`.

### D5. Missing-section detection through page render tests
Each public page has a render test, and `getSection` throws on unknown IDs, so rendering every page in CI checks every reference. That covers the spec's "page references a deleted section" scenario without a separate registry of IDs.

### D6. Drafts are filtered in the loader via `import.meta.env.PROD`
In production builds, `getSection` returns `null` for drafts and pages skip them. In other builds, drafts render inside a `TbcMarker` wrapper. Draft text still ships in the JS bundle, which is acceptable because the repository is public anyway. The guarantee is "not rendered", not "secret".

### D7. `react-markdown` with defaults, plus a link override
`react-markdown` does not render raw HTML unless `rehype-raw` is added, and we won't add it. A `components.a` override sends internal links (`/…`) through React Router's `Link` and gives external links `rel="noopener noreferrer"`.

### D8. Shared `PublicLayout` with hash scrolling
A layout route wraps the five pages and renders the header (with a mobile menu toggle), the footer and an effect that scrolls to `location.hash` after navigation. React Router doesn't do that on its own, and `/how-it-works#five-steps` has to land on the section because later changes will use it as a citation target. Page titles use React 19's native `<title>` hoisting, so no helmet dependency is needed.

### D9. Legacy anchor redirects on Home
Existing inbound links such as `/#contact` and `/#about` would otherwise land at the top of Home. Home maps the known legacy hashes to their new pages: `#contact`→`/contact`, `#about` and `#vision`→`/about`, `#platform` and `#problem`→`/how-it-works`, `#founding-partners`→`/contact#pilot`.

### D10. `/legal` follows the same one-file-per-section contract, split at subsection granularity
`page: legal` content files use the same D2 rule: one file per subsection, not one file for all of Privacy or all of Terms — e.g. `legal.privacy-legal-status`, `legal.privacy-retention`, `legal.privacy-processors`, `legal.privacy-contact`, `legal.terms-service`, `legal.terms-no-warranty`. This gives the assistant a citable ID per compliance fact instead of one undifferentiated page, which is the reason to migrate `/legal` at all. `Legal.tsx`'s `#privacy` and `#terms` anchors stay as the two on-page groupings; the route itself is unaffected.

## Risks / Trade-offs

- [Rewriting copy loses the current spec'd content, such as the anecdote] → The `landing-page` delta keeps the sector-validation requirement, including the anecdote, now placed on How it works. The page tests assert it.
- [Authors break an ID or anchor that later changes cite] → The spec treats that as a breaking content change. Once the retrieval change lands, its golden dataset will fail on a dangling ID, so the loss is caught by CI, not by visitors.
- [Draft text is visible in the bundle] → Accepted (D6). The repo is public.
- [No prerendering hurts SEO for five new URLs] → Same as today's single page. Deferred.
- [Migrating compliance-sensitive legal copy risks wording drift] → Legal content files copy `Legal.tsx`'s existing text verbatim, no rewrite. A render test asserts the migrated sections still satisfy the `privacy-policy` spec's exact-wording scenarios (retention posture, subprocessor list, contact address, legal-status statement).

## Migration Plan

Frontend only. Merging to `main` deploys through Vercel as today. Rollback is a revert. There is no data or API migration. The legacy-hash redirects (D9) keep old inbound links working.

## Open Questions

- Placement of the pilot-programme section: the Contact page (assumed) or its own block on About. Only a section file's `page` field changes.
- The TBC copy items listed in proposal.md. Each ships as `draft` and flips to `published` in a later copy-only PR.
