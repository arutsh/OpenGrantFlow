# Subprocessors

A subprocessor is a third-party service that processes personal data on
GrandFlow's behalf as part of operating the hosted platform. This list is
maintained as required by our incident-response process
(`SECURITY.md`) and referenced from the privacy policy
(`docs/legal/privacy-policy-stub.md`). New subprocessors that will
receive personal data are added here before or at the time they go live
in production.

Applies to GrandFlow's own hosted deployment. If you self-host, your
subprocessor list depends entirely on which providers you configure.

| Subprocessor | Purpose | Data received | Hosting region |
|---|---|---|---|
| [Hetzner](https://www.hetzner.com/) | Cloud infrastructure — the VPS running every backend service and the primary database | Everything stored by the platform: account data, budget/report/financial records, uploaded attachments | EU — Helsinki, Finland (`terraform/variables.tf`'s `location` variable, default `hel1`) |
| [Mailjet](https://www.mailjet.com/) | Transactional email (account verification, email-change confirmation, notifications) | Recipient name and email address, email content/template data | EU — France (Mailjet SAS) |
| [MailerSend](https://www.mailersend.com/) | Transactional email — supported as an alternate provider alongside Mailjet (`EMAIL_PROVIDER` setting, see `services/worker/tasks/users/send_verification_email.py`) | Recipient name and email address, email content/template data | EU (per provider's published documentation) — verify against MailerSend's current terms before relying on this for a compliance claim |
| [Anthropic](https://www.anthropic.com/) (and any other BYOK LLM provider a customer configures) | AI-assisted budget parsing and chat — the customer supplies their own API key (BYOK), but the request still transits GrandFlow's `ai` service on the way to the provider | Prompt content the user submits (may include budget/financial text), which can incidentally include personal data if the user includes it | US (Anthropic, PBC) — outside the EU/EEA; see the cross-border-transfer note below. Other BYOK providers a customer configures (e.g. self-hosted Ollama) have their own, separate hosting location |
| [Anthropic](https://www.anthropic.com/) — public site assistant | Answers questions anonymous visitors type into the assistant on the public website (`POST /api/v1/ai/site-assistant/ask`, off unless `SITE_ASSISTANT_ENABLED=true`). Sent under OpenGrantFlow's own platform account, not a customer's key | The visitor's question plus excerpts of OpenGrantFlow's public site content. Questions are not stored by OpenGrantFlow: they are not written to the database or audit log, and trace spans carry only chunk IDs, scores and token counts. The visitor's IP is used only as a keyed hash for daily rate limits | US (Anthropic, PBC) — see the cross-border-transfer note below. If an operator sets `SITE_ASSISTANT_PROVIDER=ollama`, questions go to that operator's own Ollama server instead |
| [Grafana Cloud](https://grafana.com/products/cloud/) | Production observability — traces, logs, and metrics (see `docs/observability/GRAFANA_CLOUD_PRODUCTION.md`) | Telemetry data (request traces, structured logs, metrics). Care is taken not to log raw PII into trace/log attributes, but identifiers such as user IDs and email addresses can appear in log lines during debugging | Depends on the Grafana Cloud stack selected at setup — check under your stack's Connections → Collector page. Confirm and record here once fixed |

## Cross-border transfer note

The production server itself is hosted in the EU/EEA (Hetzner, Helsinki,
Finland). Mailjet (France) and, per its published documentation,
MailerSend both process data within the EU as well, so no transfer
safeguard is needed for those two.

**Anthropic is based in the United States**, outside the EU/EEA. Prompt
data that transits the `ai` service on its way to Anthropic's API is a
cross-border transfer and needs an appropriate safeguard under GDPR
Chapter V (e.g., Standard Contractual Clauses — Anthropic publishes a DPA
covering this for commercial customers). The same applies to questions
visitors send through the public site assistant, which go to Anthropic
under OpenGrantFlow's own account. Any other BYOK provider a
customer configures should be assessed the same way based on where that
specific provider is hosted.

**Grafana Cloud's region is not yet confirmed here** — until it is,
treat production telemetry as a potential cross-border transfer as well
and confirm the stack's actual region.

This note does not itself constitute a compliance determination or legal
advice — it's a starting point for that assessment, to be reviewed
alongside `docs/legal/privacy-policy-stub.md`.
