# Spec Delta

## MODIFIED Requirements

### Requirement: Shared navigation on every public page
Every public page SHALL show the same header. It SHALL contain links to How it works, Security, About and Contact, plus a visually distinct "Request Demo" button linking to `/contact`. The header SHALL stay at the top of the viewport while the page scrolls. On viewports narrower than the small breakpoint, the links SHALL be reachable through a menu toggle rather than hidden.

#### Scenario: Mobile navigation
- **WHEN** a visitor on a narrow viewport opens the menu toggle
- **THEN** all four page links and "Request Demo" are visible and navigable

#### Scenario: Header while scrolling
- **WHEN** a visitor scrolls down any public page
- **THEN** the header with its links and "Request Demo" button stays visible at the top of the viewport

## ADDED Requirements

### Requirement: Privacy notice banner on public pages
When the privacy notice content is published, every public page SHALL show an inform-only banner fixed to the bottom of the viewport on a visitor's first visit. The banner SHALL state how assistant questions are retained, link to the privacy policy (`/legal#privacy`), and offer one "Got it" control that dismisses it. Dismissal SHALL be remembered in the browser against the notice's version, so a changed notice is shown again. If browser storage is unavailable, the banner SHALL still be dismissible for the current page view. The banner SHALL NOT block interaction with the page or cover the assistant's question field. The page SHALL reserve space at its foot so no content is hidden behind the banner. The banner SHALL NOT appear on authenticated app pages. When the notice content is `status: draft`, the banner SHALL NOT render in production builds.

#### Scenario: First visit
- **WHEN** a visitor opens any public page for the first time and the notice is published
- **THEN** the banner is shown at the bottom with the retention statement, a privacy-policy link and "Got it"

#### Scenario: Dismissed
- **WHEN** the visitor activates "Got it" and later opens another public page
- **THEN** the banner is not shown

#### Scenario: Notice wording changes
- **WHEN** the notice's version changes after a visitor dismissed an earlier version
- **THEN** the banner is shown again

#### Scenario: Storage blocked
- **WHEN** browser storage throws on read or write
- **THEN** the banner renders and "Got it" hides it for the current page view without an error

#### Scenario: Notice still draft
- **WHEN** the notice content is `status: draft` and the site is built for production
- **THEN** no banner is rendered

## REMOVED Requirements

### Requirement: Product demo embed remains on the home page
**Reason**: The Home page now opens with the site assistant, and the product tour is hidden until it is revisited.
**Migration**: None for visitors. The embed component stays in the codebase unrendered, so it can be restored on Home or another page later.
