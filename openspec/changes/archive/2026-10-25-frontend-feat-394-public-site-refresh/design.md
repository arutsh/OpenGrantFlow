# Design

## Context

The public site is five React pages under `frontend-typescript/src/pages/site/`, styled with Tailwind v4 utilities and the brand tokens in `src/style.css`. All copy comes from section files in `src/content/site/**`, read through `getSection()`. The site-knowledge index ingests the same directory, and the ai Dockerfile copies `content/site` only. Today `SiteAssistantBox` renders below the Home hero, only when `useSiteAssistantConfig()` reports `enabled`. The reference layout is the reviewed mockup at https://claude.ai/artifact/WFfEiDkigVbkp7Tn4YVNDM (see proposal.md, Why).

## Goals / Non-Goals

**Goals:**
- Match the mockup's layout, spacing and type sizes using Tailwind and the existing brand tokens.
- Keep every existing section `id` and `anchor`, so citations and evals stay valid.
- Keep the assistant request and response contract unchanged.

**Non-Goals:**
- Dark mode, new fonts (Inter stays first in the stack without being loaded), or a colour change.
- Status labels on answers (the mockup's "live" and "roadmap" tags). The backend doesn't return them.
- Removing the `ProductDemo` component or its content.
- Any change to the authenticated app's styling.

## Decisions

**1. Type scale as Tailwind `@utility` classes, plus a few shared site components.**
Add `text-site-display` (h1, `clamp(2.15rem, 5.4vw, 3.6rem)`), `text-site-page-title` (inner-page h1, `clamp(2rem, 4.6vw, 3rem)`), `text-site-h2` (`clamp(1.65rem, 3.4vw, 2.35rem)`), `text-site-lede` (1.2rem) and `text-site-eyebrow` (0.78rem, uppercase, tracking, teal) to `style.css`, following the existing `text-micro-label` pattern. Add small components in `components/site/`: `SectionHead` (eyebrow, h2, optional intro), `CtaBand` (navy band with heading, text and a white button) and `SiteSection` (1120px wrapper plus the mist alternate background).
*Alternative:* port the mockup's CSS as a stylesheet. Rejected because it would put a second styling system next to Tailwind.

**2. Home chooses its hero from the config query's state.**
`pending` renders a fixed-height placeholder. `success && enabled` renders `AssistantHero`. Anything else (`enabled: false`, an error, or a signed-in visitor who never fetches) renders `ClassicHero`. The query already has a 5-minute `staleTime`, so repeat visits skip the placeholder.
*Alternative:* render the classic hero while loading. Rejected because swapping a large image for the box looks broken.

**3. Suggested questions live in `src/content/assistant/suggested-questions.md`.**
The file is frontmatter only, holding `default`, `grantee`, `funder` and `technical` lists. A small loader (`lib/assistantSuggestions.ts`) parses and validates it at import time, the same way `siteContent.ts` does. A vitest suite enforces the set rules in CI. The ingestion path (`/app/content/site`) never sees this file, so no ai-service change is needed.
*Alternative:* a new `indexed: false` frontmatter flag inside `content/site`. Rejected because it needs an ingestion change and would widen the section contract for one file.

**4. The assistant box is split into parts in the same file.**
`SiteAssistantBox` keeps the mutation and state. It renders `PersonaToggle`, `SuggestedQuestions`, `AnswerBlock` and `FallbackBlock`. A suggested question calls the same `submit(question)` path as the form. UI labels (the persona label above an answer, "Answered from:", "Ask something else") stay as component constants, matching how `FALLBACK_MESSAGES` already works. Plain-text rendering stays as it is: React text nodes with `whitespace-pre-line`.

**5. The "Browse instead" section is kept, as one line of links.**
The `home.browse-instead` file stays. The fallback links in `SiteAssistantBox` read it, and its anchor is indexed. Home renders its items as the "Prefer to browse instead?" link line, carrying `id={anchor}`, so citations to `/#browse-instead` still resolve when the assistant is on.

**6. New copy goes in new section files, and existing IDs keep their files.**
New sections: `home.ask-hero` (assistant headline and lede) and one `<page>.cta` per page for the band copy, except Home, whose band reuses `home.pilot-teaser` (an eval source). Section eyebrows come from a new optional `eyebrow` frontmatter field, which ingestion ignores. Rewritten sections keep their `id`/`anchor`. `home.values-summary` grows to four items. Unconfirmed wording stays `status: draft`, so the existing `TbcMarker` handles it.
The `<page>.cta` files carry `indexed: false`, a new optional frontmatter flag that ingestion honours by skipping the section. In group 3 the indexed CTA bands outranked `security.high-risk` and `contact.demo-request` for "How do I request a demo?" and broke the pilot eval floors. A band is navigation, not a source worth citing. This reverses the reasoning in decision 3: the flag now covers one file per page, not one file, and the ingestion change is a single check.

**7. Sticky header.**
`PublicLayout`'s header gets `sticky top-0 z-20` and a background. `useHashScroll` targets need `scroll-mt-20` so anchors don't land under it.

**8. Privacy notice banner: inform-only, rendered by `PublicLayout`, with its text in `src/content/notices/privacy-banner.md`.**
The banner lives in `PublicLayout`, so it appears on public pages only and never in the app shell. The text file sits outside `content/site`, so the index never treats the notice as a citable source; the legal page stays the source for that. It reuses the draft rule from `siteContent.ts`: a draft notice renders with the TBC marker in dev and preview builds, and not at all in production. Dismissal is stored as `ogf.privacyNotice.dismissed = <version>` in `localStorage`, with reads and writes wrapped in try/catch, and a failure falls back to component state. The bar is `fixed bottom-0`, not modal, with no focus trap. `PublicLayout` adds bottom padding equal to the bar's height while it is visible, so the footer and the assistant field are never covered.
GDPR basis: the public site sets no non-essential cookies. Question storage relies on legitimate interest, so a notice is enough and no consent gate is needed. The dismissal key is a strictly necessary preference.
*Alternatives:* an opt-out control (rejected for now because it needs an API flag in the feedback change); a just-in-time notice at the box (rejected in favour of site-wide visibility).
*Timing:* the text ships as `status: draft` and is flipped to `published` together with the privacy wording in `ai-feat-site-assistant-feedback`, which ships before question storage starts. That change owns the matching wording in `legal/privacy-processors.md`, the assistant-box notice and the `privacy-policy` spec.
*Ownership:* the privacy policy holds the full account of what is stored (including country), why and how it is used; the banner stays a short summary linking to it.

## Risks / Trade-offs

- [The banner is published before the privacy policy describes storage] → It stays draft until the feedback change's privacy-wording group, and that change's task list owns flipping it. Publishing ahead of storage itself only over-discloses briefly.
- [The bar covers the bottom of the page on phones] → Reserve space with padding while it is visible, keep the text to two lines at 400px, and verify manually at that width.

- [Copy edits change the indexed text, and retrieval rankings can shift] → Re-run `services/ai/tests/evals/test_retrieval_evals.py` against the edited content in each group that changes copy, and adjust `golden_dataset.yaml` only when an expected source genuinely moved.
- [The placeholder looks empty if the config endpoint is slow] → Give it the hero's height plus the headline skeleton; the endpoint is a cheap read.
- [Anchor targets hidden under the sticky header] → Add `scroll-mt` on section wrappers, with a test that checks hash navigation still lands on the section.
- [Clash with `ai-feat-site-assistant-feedback`] → `AnswerBlock` keeps its actions in one footer row that the feedback controls can join. Whichever change lands second rebases.
- [Lint ratchet] → Files touched in `pages/site` and `components/site` must leave `BASELINE` unchanged or lower.

## Migration Plan

Frontend deploys, one per task group; group 3 also redeploys the ai service for the `indexed` check. Each group is independently revertible. No data or API migration. Ingestion re-hashes the changed sections on the next ai-service start.
