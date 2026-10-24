# Proposal

## Why

An outside draft of the public site had clearer structure, stronger copy and an assistant-first Home page. Rebuilding the site in its visual style would be a large change. Instead, this change takes the draft's layout, type scale and copy, and keeps the live site's colours, font stack, cards and buttons.
## References

- **Reviewed mockup (source of truth for layout, type sizes and copy):** https://claude.ai/artifact/WFfEiDkigVbkp7Tn4YVNDM. Private; share before others review.

## What Changes

- **Layout and type scale** on all five public pages follow the mockup: larger fluid headings, eyebrow labels, a 1120px content width, and a navy call-to-action band per page. Colours, fonts, cards and buttons are unchanged.
- **Assistant-first Home hero**: when the site assistant is enabled, the hero holds the assistant: a new headline, persona buttons ("Anyone" / "I receive grants" / "I fund grants" / "I'm technical"), suggested questions per persona and a single-line field. When the assistant is disabled or its config fails, Home shows the current hero in the new layout.
- **Suggested questions are sent to the real assistant** like typed questions. There are no pre-written answers.
- **New answer layout**: a persona label, the question as a heading, the answer, an "Answered from:" line of source links, and "Request a demo" and "Ask something else" actions. Fallback replies use the same container. The AI-processing notice stays.
- **Home sections**: the browse cards become one line of links, "What you get back" gets new copy, there are four values instead of three, and a pilot call-to-action band is added.
- **BREAKING (spec):** the product demo embed is removed from Home. The component file stays.
- **Copy updates** from the draft, keeping section IDs and anchors; unconfirmed claims stay draft.
- **Sticky header**; mobile menu kept.
- **Privacy notice banner**: an inform-only bar fixed to the bottom of every public page. It says assistant questions are kept for up to 90 days to improve answers, with personal details removed and nothing linked to an account. It links to the privacy policy and goes away once dismissed with "Got it". It ships as draft and is published with the privacy-policy wording, before question storage starts.
- Light mode only.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `public-site`: sticky header; the product demo requirement is removed; the privacy notice banner is added.
- `site-assistant-ui`: assistant-or-classic hero, suggested questions per persona, new answer and fallback layout.
- `site-content`: suggested questions and the banner text live in content files the retrieval index does not ingest.

## Impact

- **Frontend only:** `src/pages/site/*`, `components/site/PublicLayout.tsx`, `SiteAssistantBox.tsx`, a new `PrivacyNoticeBanner`, `src/style.css`, and the content under `src/content/**`.
- **Retrieval:** copy edits change the indexed text for existing IDs, so retrieval evals need a re-run.
- **Depends on `ai-feat-site-assistant-feedback`** for the banner's go-live. That change introduces question storage and updates the "not stored" wording in `legal/privacy-processors.md`, the assistant-box notice and the `privacy-policy` spec. The banner is published in the same release. Its answer footer also gains feedback controls, which this layout leaves room for.
