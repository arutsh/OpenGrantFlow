# public-site Specification

## Purpose
Defines the multi-page public website that unauthenticated visitors see (routes, shared navigation, footer, page titles and the contact page). It replaces the single scrolling landing page.
## Requirements
### Requirement: Public pages are served at dedicated routes
The public site SHALL serve these pages to unauthenticated visitors: Home at `/`, How it works at `/how-it-works`, Security & data at `/security`, About at `/about`, and Contact at `/contact`. Each route SHALL survive a hard reload or direct link. It SHALL NOT be redirected to `/dashboard` by the catch-all route.

#### Scenario: Direct link to a public page
- **WHEN** an unauthenticated visitor opens `/how-it-works` directly
- **THEN** the How it works page renders

#### Scenario: Authenticated visitor on home
- **WHEN** an authenticated user opens `/`
- **THEN** they are redirected to `/dashboard`, as today

#### Scenario: Authenticated visitor on an inner public page
- **WHEN** an authenticated user opens `/security`
- **THEN** the Security & data page renders without redirect

### Requirement: Shared navigation on every public page
Every public page SHALL show the same header. It SHALL contain links to How it works, Security, About and Contact, plus a visually distinct "Request Demo" button linking to `/contact`. The header SHALL stay at the top of the viewport while the page scrolls. On viewports narrower than the small breakpoint, the links SHALL be reachable through a menu toggle rather than hidden.

#### Scenario: Mobile navigation
- **WHEN** a visitor on a narrow viewport opens the menu toggle
- **THEN** all four page links and "Request Demo" are visible and navigable

#### Scenario: Header while scrolling
- **WHEN** a visitor scrolls down any public page
- **THEN** the header with its links and "Request Demo" button stays visible at the top of the viewport

### Requirement: Shared footer on every public page
Every public page SHALL show a footer with links to Home, How it works, Security, About, Contact, GitHub, Privacy Policy (`/legal#privacy`) and Terms (`/legal#terms`).

#### Scenario: Visitor reaches the privacy policy from any page
- **WHEN** a visitor activates "Privacy Policy" in the footer of any public page
- **THEN** they arrive at the privacy section of `/legal`

### Requirement: Each public page has a distinct document title
Each public page SHALL set a document title that names the page, e.g. "How it works · Open Grant Flow".

#### Scenario: Browser tab title
- **WHEN** a visitor navigates from Home to About
- **THEN** the document title changes to the About page title

### Requirement: Contact page collects demo requests
The Contact page SHALL provide a demo-request form with name, work email, organisation and organisation type (Nonprofit or NGO, Foundation, Institutional donor, Other) as required fields. It SHALL also have an optional free-text question about reporting time and an optional pilot-interest checkbox. The form SHALL link to the privacy policy. It SHALL show success or failure after submission.

#### Scenario: Successful demo request
- **WHEN** a visitor submits the form with all required fields
- **THEN** the request is sent, including the organisation type and pilot-interest value
- **AND** a success message replaces or accompanies the form

#### Scenario: Missing required field
- **WHEN** a visitor submits without a work email
- **THEN** the form is not sent and the field is flagged

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
