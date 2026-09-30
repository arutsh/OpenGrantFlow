## Why

The public site is one 861-line `LandingPage.tsx`, and all its copy is hard-coded in JSX. A reviewed redesign draft splits it into five pages (Home, How it works, Security & data, About, Contact). The planned site assistant (`ai-feat-site-assistant-retrieval-evals` and later) needs that same copy as addressable, versioned content, with an ID, URL, page and heading for every section. Content files give both one source of truth.

## What Changes

- Split the landing page into five public routes: `/`, `/how-it-works`, `/security`, `/about`, `/contact`. They share a header (with a mobile menu), a footer and per-page `<title>`s. `/legal` is unchanged.
- Move all public-page copy into markdown files with YAML frontmatter under `frontend-typescript/src/content/site/`, **one file per section**. Frontmatter carries a stable `id`, `page`, `anchor`, `title`, optional `personas`, a `status` (`published` | `draft`) and optional structured `items` (cards, steps, quotes, FAQs).
- Page components own the layout. Copy comes from the content loader by section ID, so a copy edit never touches TSX.
- `draft` sections render only in non-production builds, with a visible "TBC" marker. They are never rendered in production. This is how the redesign's unresolved TBC items ship safely.
- A content validation test in the existing frontend CI job fails on duplicate IDs, missing fields, or sections that pages reference but that don't exist.
- The "Request Demo" CTA and all contact links point to `/contact`. The contact form moves there and gains the organisation-type select and the pilot-interest checkbox from the redesign. It still submits through web3forms.
- The "Founding Design Partner" programme copy is renamed "Pilot Partner", following the redesign.
- **Out of scope:** the assistant input box shown in the redesign. It lands with `ai-feat-site-assistant-grounded-answers`, and no non-functional box ships before then.

## Capabilities

### New Capabilities
- `site-content`: the content-file contract (fields, ID and anchor stability, draft/published lifecycle, validation). Later changes ingest content through this contract.
- `public-site`: the multi-page public site (routes, shared navigation including mobile, footer, per-page titles, contact page).

### Modified Capabilities
- `landing-page`: the Request Demo CTA now targets `/contact` instead of `#contact`, and the sector-validation evidence moves from the home page's Problem section to the How it works page.

## Impact

- **Frontend:** `LandingPage.tsx` is replaced by `src/pages/site/*`, `src/content/site/**` and `src/lib/siteContent.ts`. `App.tsx` gains public routes, registered before the `*` → `/dashboard` catch-all. `LandingPage.test.tsx` is replaced by per-page tests and the content validation test.
- **New npm dependencies:** `react-markdown` (renders section bodies with no raw-HTML passthrough) and `yaml` (a browser-safe frontmatter parser). `gray-matter` is avoided because it needs Node `Buffer` polyfills under Vite.
- **Hosting:** Vercel (`vercel.json`) already rewrites every path to `index.html`, and so does `nginx.frontend.conf` (`try_files`), so no gateway change is needed.
- **Downstream:** `ai-feat-site-assistant-retrieval-evals` depends on this change and reads the same content files.
- **Content owner input:** the redesign's TBC items (hosting region, GDPR wording, CIC registration status, pilot month details and time expectations) ship as `draft` until confirmed. None of them blocks merging.
