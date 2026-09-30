# Spec Delta

## MODIFIED Requirements

### Requirement: Nav offers a Request Demo call-to-action
The top navigation bar SHALL include a "Request Demo" call-to-action, visually distinct from the plain text nav links (e.g. rendered as a button), that links to the Contact page (`/contact`).

#### Scenario: Visitor wants a demo from anywhere on the page
- **WHEN** a visitor views the top navigation bar
- **THEN** a "Request Demo" button is visible in the nav
- **AND** activating it navigates to the Contact page (`/contact`)

### Requirement: Problem section includes sector-validation evidence
The How it works page SHALL include a block of sector-validation content consisting of at least three anonymized pull-quotes attributed by role only (no invented names or organizations), one paraphrased first-hand anecdote visually distinguished from the verbatim quotes, and a closing statement summarizing the market opportunity.

#### Scenario: Visitor reads the problem section
- **WHEN** a visitor scrolls to the sector-validation block on the How it works page
- **THEN** they see role-attributed pull-quotes describing sector pain points
- **AND** they see a paraphrased anecdote presented without quotation marks and visually distinguished from the verbatim quotes
- **AND** they see a closing statement about the market opportunity

#### Scenario: No fabricated attribution
- **WHEN** the sector-validation block is rendered
- **THEN** no quote is attributed to a specific named person or organization that was not actually provided as source material
