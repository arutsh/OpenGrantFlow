# Tasks

Workflow rule: one task group = one GitHub sub-issue (of this change's parent issue) = one PR, merged before the next group starts.

Reference mockup for every group: https://claude.ai/artifact/WFfEiDkigVbkp7Tn4YVNDM. Its review strip switches between pages, turns the assistant on or off, and picks the assistant's response.

## 1. Site shell, type scale and Home body — ticket depends on none

- [ ] 1.0 Run `scripts/flow.py start frontend-feat-public-site-refresh 1` to move this group to In Progress and create its branch before starting any other work in this group.
- [ ] 1.1 Add the `text-site-display`, `text-site-page-title`, `text-site-h2`, `text-site-lede` and `text-site-eyebrow` utilities to `src/style.css` (design §1); verify with a page rendering each at the mockup's sizes.
- [ ] 1.2 Add `SectionHead`, `CtaBand` and `SiteSection` to `src/components/site/`, each with a render test covering heading level, eyebrow and CTA link target.
- [ ] 1.3 Make the `PublicLayout` header sticky and widen the header and footer to the 1120px wrapper. Keep the mobile menu toggle. Add `scroll-mt` so anchors clear the header; verify `PublicLayout.test.tsx` covers the sticky class and the mobile menu, and that `/how-it-works#five-steps` lands below the header.
- [ ] 1.4 Restyle the current Home hero as `ClassicHero` (headline, body, two buttons, mockup image) at the new type scale; verify `Home.test.tsx` still finds the headline, both buttons and the image.
- [ ] 1.5 Stop rendering `ProductDemo` on Home (keep the component file). Replace the demo-embed test in `Home.test.tsx` with one asserting no demo iframe is rendered.
- [ ] 1.6 Update copy in `home/what-you-get-back.md` and `home/values-summary.md` (four values) from the mockup, keeping `id` and `anchor`. Add `home/cta.md` for the pilot band. Restyle those Home sections with the card grid, `SectionHead` and `CtaBand`; verify content validation and `Home.test.tsx` pass.
- [ ] 1.7 Run `npm test`, `npm run lint:ci` and `npm run build` in `frontend-typescript`, plus `pytest tests/evals/test_retrieval_evals.py` in `services/ai`, all clean. Check Home at 400px and desktop widths; PR merged.

## 2. Assistant-first hero — ticket depends on 1

- [ ] 2.0 Run `scripts/flow.py start frontend-feat-public-site-refresh 2` to move this group to In Progress and create its branch before starting any other work in this group.
- [ ] 2.1 Add `src/content/assistant/suggested-questions.md` with the `default`, `grantee`, `funder` and `technical` sets from the mockup. Add `lib/assistantSuggestions.ts` with validation (every set present, 1–4 questions each). Its vitest suite covers a missing set, an empty set and a five-question set.
- [ ] 2.2 Rework `SiteAssistantBox` into persona toggle, suggested questions, answer block and fallback block, per the `site-assistant-ui` delta. Use the new persona labels, toggle-off, a single-line input with `maxLength` and a counter near the limit, and keep the AI-processing notice at the foot. Extend `SiteAssistantBox.test.tsx` to cover: a chip submits its text plus persona, the persona clears on a second click, the answer block order and plain-text question heading, "Ask something else" resetting, fallback with the reset action, and the notice visible before asking.
- [ ] 2.3 Add `home/ask-hero.md` (headline and lede). Build `AssistantHero` (headline, lede, box, browse-instead link line carrying the `browse-instead` anchor) and switch Home's hero on config state, with a fixed-height placeholder while pending (design §2). Remove the browse-instead cards from Home. `Home.test.tsx` covers the pending, enabled, disabled and error states and the signed-in redirect.
- [ ] 2.4 Run `npm test`, `npm run lint:ci` and `npm run build` in `frontend-typescript`, plus `pytest tests/evals/test_retrieval_evals.py` in `services/ai`, all clean. Ask a suggested question for each persona against a local ai service and confirm a real cited answer renders, then check 400px width; PR merged.

## 3. How it works and Security pages — ticket depends on 1

- [ ] 3.0 Run `scripts/flow.py start frontend-feat-public-site-refresh 3` to move this group to In Progress and create its branch before starting any other work in this group.
- [ ] 3.1 Update copy in the `how-it-works/*.md` sections from the mockup, keeping `id` and `anchor`, and add `how-it-works/cta.md`. Restyle `HowItWorks.tsx`: page hero, numbered steps list, survey evidence callout, roadmap line, two "who it's for" cards, three quote cards and `CtaBand`. Verify `HowItWorks.test.tsx` and `sectionLifecycle.test.tsx` pass.
- [ ] 3.2 Update copy in the `security/*.md` sections from the mockup, keeping `gdpr` and `data-location` as `status: draft`, and add `security/cta.md`. Restyle `Security.tsx` as question cards with an "Available now" or "Talk to us" pill and `CtaBand`. Verify `Security.test.tsx` passes and draft sections stay hidden in a production build.
- [ ] 3.3 Run `npm test`, `npm run lint:ci` and `npm run build` in `frontend-typescript`, plus `pytest tests/evals/test_retrieval_evals.py` in `services/ai`, all clean. Check both pages at 400px and desktop widths; PR merged.

## 4. About and Contact pages — ticket depends on 1

- [ ] 4.0 Run `scripts/flow.py start frontend-feat-public-site-refresh 4` to move this group to In Progress and create its branch before starting any other work in this group.
- [ ] 4.1 Update copy in the `about/*.md` sections from the mockup (origin story, mission, four values, how we are set up), keeping the CIC sentence as a draft section, and add `about/cta.md`. Restyle `About.tsx` with the two-column story layout, value cards, three model cards and `CtaBand`. Verify `About.test.tsx` passes.
- [ ] 4.2 Update copy in the `contact/*.md` sections from the mockup, keeping `faq-time` as draft. Restyle `Contact.tsx` as the navy pilot section: three month cards, receive/ask lists, demo copy beside `DemoRequestForm` in a white card, and the FAQ accordion. Leave the form's fields and submission unchanged; verify `Contact.test.tsx` passes.
- [ ] 4.3 Run `npm test`, `npm run lint:ci` and `npm run build` in `frontend-typescript`, plus `pytest tests/evals/test_retrieval_evals.py` in `services/ai`, all clean. Do a final pass over all five pages against the mockup at 400px and desktop widths (header, footer, CTA bands, anchors); PR merged.

## 5. Privacy notice banner — ticket depends on 1

- [ ] 5.0 Run `scripts/flow.py start frontend-feat-public-site-refresh 5` to move this group to In Progress and create its branch before starting any other work in this group.
- [ ] 5.1 Add `src/content/notices/privacy-banner.md` with `status: draft`, `version: 2026-10-1` and the agreed wording ("Questions you ask the assistant are kept for up to 90 days to improve answers, with personal details removed and not linked to an account." plus a privacy-policy link). Add a loader with validation, whose vitest suite covers a missing `status`, a missing `version` and an empty body.
- [ ] 5.2 Build `PrivacyNoticeBanner` and render it from `PublicLayout` (design §8): a fixed bottom bar, a "Got it" control, versioned `localStorage` dismissal with a try/catch fallback, bottom padding while visible, and a TBC marker in non-production builds when draft. `PrivacyNoticeBanner.test.tsx` covers first visit, dismissal persisting across a rerender, a version bump showing the banner again, storage throwing, draft hidden in production mode, and absence from authenticated app routes.
- [ ] 5.3 Add a task to `ai-feat-site-assistant-feedback` that flips `privacy-banner.md` to `status: published` in the group that ships the privacy wording, ahead of question storage. Verify the task appears in that change's planning files.
- [ ] 5.4 Run `npm test`, `npm run lint:ci` and `npm run build` in `frontend-typescript`, all clean. Check at 400px that the bar covers neither the assistant field nor the footer, and that "Got it" is reachable by keyboard; PR merged.
