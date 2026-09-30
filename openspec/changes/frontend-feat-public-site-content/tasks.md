# Tasks

Workflow rule: one task group = one GitHub sub-issue (of this change's parent issue) = one PR, merged before the next group starts.

## 1. Content contract, loader and first content-driven pages (How it works, Security & data)

- [ ] 1.0 Run `scripts/flow.py start frontend-feat-public-site-content 1` to move this group to In Progress and create its branch before starting any other work in this group.
- [ ] 1.1 Add `react-markdown` and `yaml` to `frontend-typescript/package.json`; verify `npm ci` and `npx vitest run` still pass.
- [ ] 1.2 Implement `src/lib/siteContent.ts` (D4, D6): eager `?raw` glob of `src/content/site/**/*.md`, frontmatter split, contract validation, `getSection(id)` throwing on unknown IDs, and draft filtering by `import.meta.env.PROD`. Verify with `siteContent.test.ts` covering: missing field, bad `page`/`status`/`personas` value, duplicate `id`, duplicate anchor on the same page, draft hidden when PROD is stubbed true and shown when false.
- [ ] 1.3 Add a `SiteMarkdown` component (D7) and a `TbcMarker` wrapper. Verify with tests that raw `<script>`/HTML in a body produces no element, internal links render as router links, and external links get `rel="noopener noreferrer"`.
- [ ] 1.4 Add `PublicLayout` (D8): shared header with the mobile menu toggle, footer (spec links including `/legal#privacy` and `/legal#terms`), and hash scrolling. Verify with tests that the mobile toggle exposes all nav links and that `/how-it-works#five-steps` scrolls to that section (`scrollIntoView` spy).
- [ ] 1.5 Author the How it works content files from the redesign: intro, five steps, survey evidence, roadmap, "who it's for" (grantee and funder items), and the sector-validation block (≥3 role-attributed quotes, the existing paraphrased anecdote carried over from `LandingPage.tsx`, the closing statement). Build `src/pages/site/HowItWorks.tsx` on it. Verify with a render test covering the `landing-page` sector-validation scenarios.
- [ ] 1.6 Author the Security & data content files, with TBC items (GDPR wording, data location) as `status: draft`, and build `src/pages/site/Security.tsx`. Verify with a render test that draft sections are absent under a PROD stub.
- [ ] 1.7 Register `/how-it-works` and `/security` under `PublicLayout` in `App.tsx`, before the `*` catch-all, with per-page `<title>`s. Verify with a routing test that a direct visit renders each page for both an anonymous and an authenticated user, and that each title is set.
- [ ] 1.8 Add a short author guide at `src/content/site/README.md` (fields, ID/anchor stability rule, draft lifecycle). Verify it matches the `site-content` spec fields.
- [ ] 1.9 Run `npx vitest run`, `npm run lint` and `npx tsc --noEmit -p tsconfig.app.json` in `frontend-typescript` clean; PR merged.

## 2. About and Contact pages — ticket depends on 1

- [ ] 2.0 Run `scripts/flow.py start frontend-feat-public-site-content 2` to move this group to In Progress and create its branch before starting any other work in this group.
- [ ] 2.1 Author the About content files (mission, origin story, values, "how we are set up" with the CIC status as `draft`, open-code link) and build `src/pages/site/About.tsx`. Verify with a render test.
- [ ] 2.2 Author the Contact content files: pilot programme (`anchor: pilot`, with month details as `draft`), what you receive and what we ask, demo-request intro, and FAQ items (the time-expectations answer as `draft`).
- [ ] 2.3 Build `src/pages/site/Contact.tsx` with the demo-request form moved out of `LandingPage.tsx`. Add the organisation-type select, the optional reporting-time question and the pilot-interest checkbox, all sent through the existing web3forms submission. Verify with tests for the successful-submit (mocked `fetch`, payload includes the new fields) and missing-work-email scenarios.
- [ ] 2.4 Register `/about` and `/contact` in `App.tsx` with titles. Point every "Request Demo" CTA, including the current landing nav, to `/contact`. Verify with the routing test and a nav test asserting `href="/contact"`.
- [ ] 2.5 Run `npx vitest run`, `npm run lint` and `npx tsc --noEmit -p tsconfig.app.json` in `frontend-typescript` clean; PR merged.

## 3. Home page from content and retirement of the single-page landing — ticket depends on 1, 2

- [ ] 3.0 Run `scripts/flow.py start frontend-feat-public-site-content 3` to move this group to In Progress and create its branch before starting any other work in this group.
- [ ] 3.1 Author the Home content files (hero, "browse instead" links, what you get back, values summary, pilot teaser) and build `src/pages/site/Home.tsx` under `PublicLayout`. Keep the product demo embed and the authenticated redirect to `/dashboard`. Verify with render tests for the demo iframe, the absence of any in-development status pill, and the authenticated redirect.
- [ ] 3.2 Add the legacy hash redirects on Home (D9). Verify with a test per legacy hash (`#contact`, `#about`, `#vision`, `#platform`, `#problem`, `#founding-partners`).
- [ ] 3.3 Delete `LandingPage.tsx` and `LandingPage.test.tsx`, and move every assertion still relevant into the new page tests. Verify with `grep -rn "LandingPage" frontend-typescript/src` returning nothing, and confirm no copy string remains hard-coded in `src/pages/site/*.tsx` (only section IDs).
- [ ] 3.4 Run a production build check (`npx vite build`, then `npx vite preview`). Manually verify all five routes and a hard reload on `/security#…`, confirm no TBC marker or draft copy is visible, and confirm the mobile menu works at phone width.
- [ ] 3.5 Run `npx vitest run`, `npm run lint` and `npx tsc --noEmit -p tsconfig.app.json` in `frontend-typescript` clean; PR merged.
