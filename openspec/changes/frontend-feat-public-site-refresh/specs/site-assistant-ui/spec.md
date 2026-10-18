# Spec Delta

## MODIFIED Requirements

### Requirement: Assistant box appears on Home only when enabled
When the site assistant's config reports `enabled: true`, the Home page SHALL use the assistant box as its hero: a headline and lede, the persona toggle and the box, followed by links to How it works, Security & data and About. While the config is loading, the hero SHALL show a placeholder of the same height, with no box and no classic hero, so the page does not jump when the config arrives. When the config is disabled or cannot be loaded, the Home page SHALL show the classic hero instead: the headline, the two call-to-action buttons and the product image. It SHALL show no assistant box and no error.

#### Scenario: Assistant enabled
- **WHEN** a visitor opens Home and the config reports `enabled: true`
- **THEN** the hero contains the assistant box and the classic hero is not shown

#### Scenario: Config still loading
- **WHEN** a visitor opens Home and the config request has not answered yet
- **THEN** neither the assistant box nor the classic hero is shown, and the rest of the page renders below the hero area

#### Scenario: Assistant disabled
- **WHEN** a visitor opens Home and the config reports `enabled: false`
- **THEN** the classic hero is shown, no assistant box is shown, and the rest of the page renders normally

#### Scenario: Config request fails
- **WHEN** the config request returns an error
- **THEN** the classic hero is shown and no error is displayed

### Requirement: Visitor can ask with an optional persona
The box SHALL offer a persona toggle with the labels "I receive grants" (`grantee`), "I fund grants" (`funder`) and "I'm technical" (`technical`). No persona is selected at first, and activating the selected persona again SHALL clear it. The question field SHALL be limited to the configured maximum length. Submitting SHALL send the question and the selected persona, if any, and SHALL disable the submit control until the response arrives.

#### Scenario: Persona sent with the question
- **WHEN** a visitor selects "I fund grants" and submits a question
- **THEN** the request carries `persona: funder`

#### Scenario: Persona cleared
- **WHEN** a visitor activates the already-selected persona
- **THEN** no persona is selected and the next request carries no persona

#### Scenario: Length limit enforced in the field
- **WHEN** the configured maximum is 500 characters
- **THEN** the field accepts no more than 500 characters

### Requirement: Answers show their sources
For `answerable: true`, the box SHALL replace the suggested questions with an answer block. The block SHALL show, in order: a label naming the selected persona, or a generic label when none is selected; the visitor's question as a heading; the answer text; an "Answered from:" line with one link per citation; and two actions, "Request a demo" (linking to `/contact`) and "Ask something else". Each citation link SHALL be labelled with the citation title and point at its URL. The answer text and the question heading SHALL be rendered as plain text, never as HTML. "Ask something else" SHALL clear the answer and the field and show the suggested questions again.

#### Scenario: Cited answer
- **WHEN** the response has `answerable: true` and two citations
- **THEN** the box shows the question heading, the answer and two source links to the cited URLs on the "Answered from:" line

#### Scenario: Markup in answer text
- **WHEN** the answer text or the question contains HTML tags
- **THEN** the tags are shown as literal text and not interpreted

#### Scenario: Ask something else
- **WHEN** a visitor activates "Ask something else" after an answer
- **THEN** the answer is removed, the field is empty and focused, and the suggested questions are visible

### Requirement: Browse-instead fallback
When the response has `answerable: false`, or the request fails with 429, 503 or any other error, the box SHALL show a short message and links to the public site's main pages in the answer block, with the "Ask something else" action, instead of an answer.

#### Scenario: Unanswerable question
- **WHEN** the response has `answerable: false`
- **THEN** the box shows the "couldn't find that" message with browse links

#### Scenario: Daily cap reached
- **WHEN** the request returns 429
- **THEN** the box shows a "try again tomorrow" message with browse links

## ADDED Requirements

### Requirement: Suggested questions per persona
The box SHALL show up to four suggested questions as buttons. The set shown SHALL depend on the selected persona, with a default set when no persona is selected. Activating a suggested question SHALL put its text in the question field and submit it the same way as a typed question, with the selected persona. The answer SHALL come from the assistant; the box SHALL NOT show pre-written answers.

#### Scenario: Persona changes the suggestions
- **WHEN** a visitor selects "I'm technical"
- **THEN** the suggested questions change to the technical set

#### Scenario: Suggested question is sent to the assistant
- **WHEN** a visitor with "I receive grants" selected activates a suggested question
- **THEN** a request is sent with that question's text and `persona: grantee`
- **AND** the answer shown is the assistant's response
