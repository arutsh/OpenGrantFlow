# For NGOs & Grantees

> Part of the [Open Grant Flow User Guide](./README.md) · See also: [Donor / Funder Guide](./donor-guide.md)

This guide covers the day-to-day workflow for an organisation managing budgets and reporting to donors.

## 1. Your dashboard

The Grantee dashboard gives you a portfolio-level view of everything you manage:

- **Budgets by status** — A composition bar showing how many budgets you have in each status (Draft, AI Draft, Confirmed, Archived).
- **Confirmed, received & converted** — For each donor currency you work in, how much is confirmed, how much has actually been received, and what share has been converted to your local currency — kept separate per currency rather than blended into one misleading total.
- **Budget breakdown** — A line-by-line table of every confirmed budget showing the donor, the converted total, spend so far, a burn-rate bar, and what's remaining.

## 2. Creating a budget

There are three ways to start a budget — use whichever fits the situation.

### Manually
Click **"Add Budget"** and build it line by line: category, description, amount, currency, and duration.

### AI budget assistant ("Ask, don't build")
Describe what you need in plain language in the AI Budget Assistant panel — for example, *"set up a 12-month youth program budget in GBP"* — and Open Grant Flow drafts the full budget structure for you. AI-generated budgets are created in **AI Draft** status so you can review and adjust every line before confirming.

### Import from Excel
Upload your existing `.xlsx` budget file directly. The platform recognises previously-seen donor template layouts automatically, and for anything it hasn't seen before, an AI extraction step reads the sheet and maps categories, descriptions, amounts, and currencies into a structured budget — arriving as an **AI Draft**. Anything it isn't fully confident about is preserved rather than dropped, so you can review it instead of losing data silently.

> **Note:** Excel extraction uses your organisation's own AI key if you've configured one (see [Settings → AI Integrations](./README.md#24-ai-integrations-bring-your-own-key)), and otherwise falls back to a platform-funded model automatically — you're never blocked from importing just because AI isn't set up yet.

### Grouped vs. List view

Above the Budget Lines table, toggle between **Grouped** (lines rolled up under their category, with an inline rename control next to each category name) and **List** (a flat view of every line — rename isn't available here, since a category can span more than one place in the list). On mobile, lines are always shown grouped by category regardless of this toggle.

## 3. Budget statuses

| Status | Meaning |
|---|---|
| **Draft** | Being built manually; not yet visible as committed to a donor. |
| **AI Draft** | Created via the AI assistant or Excel import; awaiting your review before confirming. |
| **Confirmed** | Locked in with a start date. Unlocks reporting against this budget. |
| **Archived** | Retired from active use. Can be restored later if needed. |

Confirming a budget sets a start date and moves it from Draft/AI Draft to Confirmed — either you or your matching donor can do this, so whoever finalises the agreement first can lock it in. Confirming is what unlocks the Reports section for that budget. An archived budget isn't gone — it can be restored, and returns to Confirmed (if it was already confirmed) or Draft otherwise.

## 4. Understanding the currencies on a budget

Open Grant Flow tracks money in up to three currency contexts at once, deliberately kept separate rather than blended into one figure that would hide what's really happening:

- **Donor commitment (actual currency)** — What the donor has committed, in the donor's currency — entered directly, not derived.
- **Local total** — The sum of your budget lines, in your own operating currency.
- **Estimated exchange rate** — A rate you set yourself to guide planning — it's your estimate, not a live market rate, and it's saved as soon as you enter it so a half-built budget never loses it.
- **Estimated local cap** — Donor commitment × your estimated rate — calculated automatically, never stored, so it always reflects your latest rate.

Separately, once a budget is confirmed, you can record real **funding receipts** (money that's actually landed) and real **currency conversions** (an actual bank FX transaction, with the rate derived from the two real amounts — not typed in). As you log expenses against reports, each expense draws down against these real conversion "lots", oldest first, so you can always trace which specific bank conversion funded which expense. If an expense is bigger than what's been converted so far, it's still recorded — Open Grant Flow won't block an overspend, it just shows the shortfall honestly, and a later conversion will automatically settle it retroactively.

## 5. Reports & receipts

### Creating a report
Once a budget is **Confirmed**, open it and start a new report against a specific reporting period (or leave it blank to cover the full budget span). Reporting periods can't overlap an existing report on the same budget, so your reporting history stays a clean, non-duplicated timeline.

### Adding report lines
Each report line links to a specific budget line, with a description, an amount, and the expense date (when the money was actually spent — not when you happen to be logging it). The expense date must fall inside the report's period.

### Attaching evidence
Attach one or more files per report line as proof — receipts, invoices, payment confirmations. Accepted formats are **PDF, JPEG, PNG, and HEIC**, up to **15MB** each. Attachments can only be added or removed while the report is still in Draft.

### Submitting for review
When a report is complete, submit it. This moves it from Draft to Submitted and locks its lines and attachments from further edits. Your donor then reviews it and either approves it or rejects it with review notes explaining what needs fixing. A rejected report stays in Rejected status until you explicitly reopen it, which moves it back to Draft so you can correct it and resubmit.

| Report status | What it means |
|---|---|
| **Draft** | Being built; lines and attachments are editable. |
| **Submitted** | Sent for donor review; locked from further edits. |
| **Approved** | Accepted by the donor. |
| **Rejected** | Sent back with review notes; reopen it to return to Draft for corrections. |

## 6. Reports directory

The **"Reports"** item in the sidebar gives you a single cross-budget view of every report you own — with its budget, donor, period, and status — filterable by status, budget, and donor, so you don't have to open each budget individually to check where things stand.

## 7. Exporting to Excel

From a budget's detail view, click the export icon to download it as a formatted `.xlsx` workbook. It's available to whoever can already view the budget — its owner and its funder — and reflects the budget's data at the moment you download it (it isn't a live-synced file, so re-export to get a later snapshot).

The workbook has three sheets:

- **Original Budget** — the budget as planned, by category and line, with totals as live formulas rather than fixed numbers — open it in Excel or LibreOffice and edit the exchange-rate cell to see every total recalculate.
- **Budget vs. Report Dashboard** — a donor-currency view of what's been received, converted, and spent against what was approved, plus the current balance. Any figure that blends a real bank-conversion rate with your estimated rate (because not every expense has been converted yet) is flagged with an asterisk and a footnote, never blended in silently.
- **List of Expenses** — every reported expense, one row per report line (or one row per currency-conversion lot it drew from, when it drew from more than one) — the same lot-by-lot trace described in [§4](#4-understanding-the-currencies-on-a-budget), laid out for offline reference.

---

*See also: [Getting Started & Settings](./README.md) · [Donor / Funder Guide](./donor-guide.md)*
