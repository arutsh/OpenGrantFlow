# Spec Delta

## MODIFIED Requirements

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
