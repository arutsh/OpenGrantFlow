## Why

After launch, the assistant will fail in ways the golden dataset didn't predict, and today `/ask` keeps nothing to learn from. This change closes the loop: production question → review → new eval case → fix → permanent regression test, gated by `ai-feat-site-assistant-release-gates`.

## What Changes

- **Personal-details removal:** a best-effort regex redactor removes emails, phone numbers, IBANs, card-like numbers, IP addresses and URL query strings before retrieval, the model call and storage. Names are not reliably caught, so the notice still asks visitors not to include personal details.
- **Every question is stored:** each `ask` writes one record with the redacted question, persona, country code, retrieved IDs and scores, outcome, answer, model and prompt version. Questions that short-circuit below the score threshold are stored too, since they show content gaps. The response gains an `answer_id`. A failed write never blocks the answer. The privacy wording ships before storage does.
- **Country, not IP:** a local GeoIP lookup gives the country code; the IP is never stored.
- **Feedback capture:** thumbs up/down on each answer, with optional reasons (incorrect, didn't answer, outdated, missing information, other) and no free text, attached to the record by `answer_id`.
- **90-day retention:** records and feedback are purged automatically by a Celery beat task alongside `cleanup-ai-sessions-daily`, registered in the worker's `include=[]`.
- **Review → dataset CLI:** a superuser CLI lists negative feedback and short-circuited questions, and promotes a record into the golden dataset as a new eval case with its expected sources. Promotion needs the operator to confirm or rewrite the question, and the entry keeps no record ID, country or timestamp.
- **Privacy wording:** the policy's collected-information, use, retention and processors sections state what is stored, why and how. The "not stored" wording in the legal page and box notice is replaced, and the public-site-refresh banner is published in the same release.

## Capabilities

### New Capabilities
- `site-assistant-feedback`: redaction, question records, country lookup, feedback capture, retention purge and the review CLI.

### Modified Capabilities
- `site-assistant`: the response gains `answer_id`; the length limit applies before redaction.
- `site-assistant-ui`: feedback controls on answers; the notice states the 90-day retention.
- `retrieval-evaluation`: dataset entries gain `source` (`authored` or `production`), with metrics broken down per source.
- `privacy-policy`: the retention requirement allows the enforced 90 days; the processors requirement drops "not stored"; a new requirement discloses what is stored, why and how.

## Impact

- **Depends on:** `ai-feat-site-assistant-release-gates` (promoted cases need a working gate to become regression tests).
- **Coordinated with:** `frontend-feat-public-site-refresh`, whose draft banner this change's release publishes; whichever lands second rebases the answer footer.
- **Related:** `gdpr-iso27001-priority-2` (may later absorb the purge task).
- **ai service:** record model and migration, feedback endpoint, redactor, GeoIP lookup, review CLI.
- **worker:** the purge beat task.
- **frontend:** feedback controls, notice text, privacy sections under `content/site/legal/`.
- **Dependencies:** `maxminddb` and the free DB-IP Lite country database (CC BY 4.0).
