# privacy-policy Specification

## Purpose
TBD - created by archiving change high-privacy-policy-mailjet-compliance. Update Purpose after archive.

## Requirements
### Requirement: Privacy Policy states data retention posture
The Privacy Policy SHALL describe, in qualitative terms, how long personal
data is retained, given that no fixed retention schedule is currently
enforced by the system.

#### Scenario: Retention section present without invented numbers
- **WHEN** a user reads the Privacy Policy
- **THEN** it states that data is retained only as long as needed to
  provide the service or meet legal/institutional record-keeping
  obligations, without citing a specific number of days that no system
  behavior currently enforces

### Requirement: Privacy Policy lists third-party processors
The Privacy Policy SHALL identify the third-party processors that may
handle personal data on the platform's behalf, consistent with
`docs/security/subprocessors.md`.

#### Scenario: Processors section reflects the current subprocessor list
- **WHEN** a user reads the Privacy Policy
- **THEN** it names each current subprocessor (Hetzner, Mailjet,
  MailerSend, Anthropic for BYOK AI, Grafana Cloud) and, for Anthropic,
  notes that data may cross into the US

#### Scenario: Site assistant questions are disclosed
- **WHEN** a visitor reads the Privacy Policy while the site assistant is enabled
- **THEN** it states that questions typed into the website assistant are sent
  to Anthropic under the platform's own account, may cross into the US, and
  are not stored by the platform

### Requirement: Privacy Policy provides a reachable contact
The Privacy Policy SHALL provide a named contact address for privacy
questions, in addition to the general contact form.

#### Scenario: Contact section names an address
- **WHEN** a user reads the Privacy Policy's Contact section
- **THEN** it lists `privacy@opengrantflow.com` alongside the existing
  contact form as ways to reach the maintainer about privacy questions

### Requirement: Privacy Policy states current legal status
The Privacy Policy SHALL accurately state that Open Grant Flow is not
currently operated by a registered legal entity.

#### Scenario: Legal status section present
- **WHEN** a user reads the Privacy Policy
- **THEN** it states that the project is operated by its maintainer as an
  open-source project and is not yet a registered company or nonprofit,
  without implying a legal entity exists today
