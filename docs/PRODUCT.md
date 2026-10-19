# GrantFlow — Product Overview

> **The financial infrastructure layer connecting NGOs and their donors.**
> Open-source · AI-powered · Built from 20 years of lived experience.

---

## The Problem

Every grant cycle, NGOs around the world repeat the same painful process:

- A donor sends their budget template — a unique Excel file with its own structure, formulas, and formatting rules
- The NGO manually reformats their finances to match it
- The file goes back and forth by email, with comments like "formula broken in cell D14" or "column headers don't match"
- The accountant learns yet another donor's format — work that has nothing to do with financial oversight
- The same process repeats for every donor, every cycle

**3–7 days of staff time. Per donor. Per reporting period.**

This isn't a minor inconvenience — it's a structural failure. Organisations doing the most important work in the world are spending their scarcest resource on administrative overhead that enterprise software eliminated decades ago.

---

## What GrantFlow Does

GrantFlow connects NGOs and donors inside a shared financial platform — so both sides work in their own way, and the platform handles the translation between them.

```
Donor publishes their requirements
         ↓
NGO manages finances in their own format inside GrantFlow
         ↓
Platform auto-converts between donor format and NGO format
         ↓
Donor receives clean reports in their preferred format — automatically
```

No more emailing spreadsheets. No broken formulas. No version chaos.

Budget approval, amendments, receipts, and final reports — all tracked, auditable, and submitted inside the platform.

---

## Who It's For

### NGOs and Nonprofits
- Manage all your grants and donors in one place
- Generate budgets in plain language — AI builds the structure
- Submit reports directly from the platform in whatever format your donor requires
- Track every amendment, receipt, and version automatically

### Donors and Foundations
- See your entire grantee portfolio in one dashboard
- Receive standardised reports automatically — in your preferred format
- Track budget vs actuals in real time across all grantees
- No more chasing Excel files by email

---

## Core Features

| Feature | What it does |
|---|---|
| **Centralised budget management** | All grants, donors, and budgets in one place — with version history built in |
| **AI-assisted budget generation** | Describe your budget in plain language; Open Grant Flow drafts the structured version in seconds, ready for you to review |
| **Structured Excel exports** | Export any budget as a structured Excel file, easy to copy into your funder's own format |
| **Reporting against approved budgets** | Submit reports, track amendments, attach receipts — all inside the platform |
| **Multi-provider AI** | Connect Anthropic Claude, or run fully offline with Ollama |
| **Bring Your Own Key (BYOK)** | Use your own AI provider credentials — your data stays under your control |
| **Self-hosted option** | Run entirely on your own infrastructure via Docker — no data leaves your servers |
| **Full audit log** | Every AI request, every budget change, every submission — logged and traceable |

---

## Why Open Source?

The organisations that need this most — small NGOs, grassroots groups, organisations in the global south — are exactly the ones who can't afford enterprise software.

GrantFlow is open source because the infrastructure that makes philanthropy work should belong to the sector, not to a vendor.

**Pricing:** not yet set. We're in the early stages of working with pilot partners, and our pricing structure will take shape alongside them. Our intention is for Open Grant Flow to be free for small, grassroots organisations. Piloting is free: pilot partners pay nothing.

---

## Current Status

> **Active development — not yet production-ready.**

| Phase | Status | Timeline |
|---|---|---|
| Backend APIs & core services | In progress | Now – 6 months |
| AI budget generation | Working (dev) | Now – 6 months |
| Frontend budget editor | In progress | 6–12 months |
| Automated donor exports | Planned | 6–12 months |
| Public open-source release | Planned | 12–18 months |
| Cloud hosting option | Planned | 12–18 months |

---

## The Story Behind It

Open Grant Flow is built by a team with 17 years of experience co-founding and leading nonprofit organisations, combined with senior software engineering.

We've reviewed hundreds of NGO budgets, and every one was managed in scattered Excel files and reformatted by hand for every donor. We know this pain from both sides of the table: as the people responsible for the budget, and as engineers who knew there was a better way.

The architecture reflects both worlds: production-grade microservices, multi-provider AI infrastructure, and a vendor-agnostic observability stack — built with the operational constraints of real NGOs in mind.

---

## Get Involved

### Pilot Partners
If you're an NGO or donor willing to test GrantFlow in a real grant cycle, your feedback directly shapes the product. [Open an issue](../../issues) or get in touch through the [contact page](https://opengrantflow.com/contact).

### Grant Funding
Seeking development grants (Innovate UK, FCDO, nonprofit tech foundations) to accelerate full-time development.

### Contributors
Developers, designers, and domain experts from the nonprofit sector are welcome. See [CONTRIBUTING](../../blob/main/README.md#contributing) for how to get started.

---

## Links

- [Architecture & technical docs](../../blob/main/README.md)
- [Discussions](../../discussions)
- [Issues](../../issues)
- [Contact](https://opengrantflow.com/contact)
