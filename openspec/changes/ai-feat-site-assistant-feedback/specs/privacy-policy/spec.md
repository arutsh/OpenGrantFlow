# Spec Delta

## MODIFIED Requirements

### Requirement: Privacy Policy states data retention posture
The Privacy Policy SHALL describe, in qualitative terms, how long personal data is retained in general, and SHALL state a specific period only where system behavior enforces it. For website-assistant questions it SHALL state the enforced 90-day period, and that a reviewer may keep an adapted, anonymised version of a question as a permanent test case.

#### Scenario: Retention section present without invented numbers
- **WHEN** a user reads the Privacy Policy
- **THEN** it states that data is retained only as long as needed to provide the service or meet legal/institutional record-keeping obligations, and cites no number of days that no system behavior enforces

#### Scenario: Assistant question retention stated
- **WHEN** a visitor reads the retention section
- **THEN** it states that assistant questions and feedback are deleted after 90 days, and that a reviewer may keep an adapted question, with no link to when or where it was asked, as a test case

### Requirement: Privacy Policy lists third-party processors
The Privacy Policy SHALL identify the third-party processors that may handle personal data on the platform's behalf, consistent with `docs/security/subprocessors.md`.

#### Scenario: Processors section reflects the current subprocessor list
- **WHEN** a user reads the Privacy Policy
- **THEN** it names each current subprocessor (Hetzner, Mailjet, MailerSend, Anthropic for BYOK AI, Grafana Cloud) and, for Anthropic, notes that data may cross into the US

#### Scenario: Site assistant questions are disclosed
- **WHEN** a visitor reads the Privacy Policy while the site assistant is enabled
- **THEN** it states that questions typed into the website assistant are sent to Anthropic under the platform's own account and may cross into the US, and that personal details such as email addresses and phone numbers are removed before they are sent

## ADDED Requirements

### Requirement: Privacy Policy discloses assistant question storage
The Privacy Policy SHALL state, for website-assistant questions:
- **what is stored:** the question with personal details removed, the chosen persona, the visitor's country (derived from the IP address, which is not kept), the answer and its sources, and any feedback
- **why:** to evaluate and improve the assistant's answers
- **how it is used:** reviewed by the maintainer, and turned into anonymised test cases
- **the basis:** legitimate interest
- that records are not linked to an account
- that removal of personal details is best effort, so visitors should not include personal details

It SHALL credit the IP-to-country database as its licence requires.

#### Scenario: Collected-information section
- **WHEN** a visitor reads the "Information we collect" section
- **THEN** it lists the stored assistant fields, including country, and states that the IP address is not stored

#### Scenario: Use section
- **WHEN** a visitor reads the "How we use it" section
- **THEN** it states the evaluation purpose, the review and test-case use, and the legitimate-interest basis
