# Spec Delta

## MODIFIED Requirements

### Requirement: Visitors are told where questions go
The box SHALL show a short notice, with a link to the privacy policy, stating that questions are processed by an AI provider and are kept for up to 90 days to improve answers, with personal details removed and not linked to an account.

#### Scenario: Notice visible before asking
- **WHEN** the assistant box is shown
- **THEN** the AI-processing notice and privacy-policy link are visible without submitting a question

#### Scenario: Notice states retention
- **WHEN** the assistant box is shown
- **THEN** the notice states the 90-day retention and the removal of personal details

## ADDED Requirements

### Requirement: Feedback controls on answers
For a response with `answerable: true` and a non-null `answer_id`, the answer SHALL show thumbs-up and thumbs-down controls. Choosing thumbs-down SHALL offer the reasons (incorrect, didn't answer, outdated, missing information, other) as optional single-choice buttons, with no free-text field. A submitted rating SHALL show a short thank-you in place of the controls. A failed submission SHALL show nothing beyond restoring the controls, and SHALL never replace or hide the answer.

#### Scenario: No answer ID
- **WHEN** a response has `answer_id: null`
- **THEN** no feedback controls are shown

#### Scenario: Fallback reply
- **WHEN** a response has `answerable: false`
- **THEN** no feedback controls are shown

#### Scenario: Thumbs down with reason
- **WHEN** a visitor chooses thumbs-down and then "outdated"
- **THEN** one feedback request is sent with `rating: down` and `reason: outdated`, and a thank-you is shown

#### Scenario: Feedback request fails
- **WHEN** the feedback request returns an error
- **THEN** the answer stays visible and the controls are shown again
