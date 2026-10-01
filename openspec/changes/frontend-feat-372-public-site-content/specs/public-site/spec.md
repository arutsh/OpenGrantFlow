# Spec Delta

## Purpose

Defines the multi-page public website that unauthenticated visitors see (routes, shared navigation, footer, page titles and the contact page). It replaces the single scrolling landing page.

## ADDED Requirements

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
Every public page SHALL show the same header. It SHALL contain links to How it works, Security, About and Contact, plus a visually distinct "Request Demo" button linking to `/contact`. On viewports narrower than the small breakpoint, the links SHALL be reachable through a menu toggle rather than hidden.

#### Scenario: Mobile navigation
- **WHEN** a visitor on a narrow viewport opens the menu toggle
- **THEN** all four page links and "Request Demo" are visible and navigable

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

### Requirement: Product demo embed remains on the home page
The Home page SHALL keep the existing interactive product demo embed.

#### Scenario: Visitor views the demo
- **WHEN** a visitor loads `/`
- **THEN** the product demo iframe is present
