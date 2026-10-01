# Open Grant Flow — User Guide

> A shared financial record for donors and NGOs — budgets, receipts, reports, and audit trail in one platform.

**Status:** Open Grant Flow is under active development. Some features described here may still be evolving, and this guide reflects the platform's current functionality rather than a finished, locked product.

**Last reviewed:** 2026-09-25

This guide is split by audience:

- **[Getting Started](#1-getting-started)** and **[Account & Organisation Settings](#2-account--organisation-settings)** — everyone
- **[NGO / Grantee Guide](./ngo-guide.md)** — organisations managing budgets and reporting to donors
- **[Donor / Funder Guide](./donor-guide.md)** — organisations funding grantees

---

## 1. Getting Started

Open Grant Flow works the same way whether you're an NGO managing grants or a donor funding them — you sign up once, and the platform shows you the right dashboard based on your organisation's role.

### 1.1 Creating an account

1. Go to the sign-up page and register with your name and email.
2. Verify your email address (a verification link is sent automatically).
3. Complete onboarding: enter your first name, last name, and your organisation's name.

Completing onboarding with a new organisation name automatically creates that organisation and makes you its first **Admin** — you don't need anyone's approval to get started.

### 1.2 Joining an existing organisation

If a teammate has already set up your organisation, an Admin can invite you directly by email from **Settings → Team**. You'll receive a link to accept the invitation and set your own password — you don't go through the "create an organisation" step.

### 1.3 NGO, donor, or both?

Every organisation in Open Grant Flow can be flagged as a grantee (NGO), a donor, or both. This isn't a plan you choose — it reflects how your organisation actually uses grants:

- **Grantee** — Your organisation manages budgets funded by others (the common NGO case).
- **Donor** — Your organisation funds other organisations' budgets (the common foundation/funder case).
- **Both** — Some organisations — e.g. an intermediary NGO that re-grants funds — are legitimately both, and get a toggle at the top of their dashboard to switch views.

> **Note:** If you believe your organisation's role is set up incorrectly, an Admin can raise this from Settings, or contact the Open Grant Flow team while the platform is still in active development.

---

## 2. Account & Organisation Settings

Settings are organised into personal and organisation-level sections. What you see depends on your role.

### 2.1 Personal settings

- **Profile** — Name, contact details.
- **Security** — Password and login security.
- **Privacy** — Data and privacy preferences.
- **Notifications** — What you're notified about and how.

### 2.2 Organisation profile (Admins)

Admins can edit the organisation's general details from **Settings → Organization**.

### 2.3 Team management (Admins)

Admins can invite teammates by email from **Settings → Team**. Invited teammates appear as "pending" until they accept and set a password. Admins can also remove teammates — this follows the same secure removal process used for account-deletion requests, and Open Grant Flow won't let an organisation be left with zero Admins.

### 2.4 AI integrations (Bring Your Own Key)

From **Settings → AI Integrations**, your organisation can connect its own AI provider so budget generation and Excel import run on your own credentials rather than a shared platform key:

- **Anthropic (cloud)** — Connect an Anthropic API key, used for AI-assisted budget creation. Keys are encrypted at rest and never exposed in the interface.
- **Ollama (self-hosted)** — Point to a local Ollama instance for fully offline AI processing — nothing leaves your own infrastructure. This is the option for organisations with strict data-governance requirements.

For most AI features — including the AI budget assistant — your organisation needs its own configured key. The one exception is CSV/Excel import: if you haven't configured a key, importing a spreadsheet still works by falling back to a platform-funded model, rate-limited per organisation, so you're never blocked from getting a budget out of an existing file while you're still setting up your own key.

If your organisation doesn't have a key configured and needs AI features beyond import, you can request that one be set up for you — this is handled case by case rather than automatically.

### 2.5 Billing (Admins)

Organisation-level billing and subscription details live under **Settings → Billing**.

---

## 3. Roles & Permissions at a Glance

| Role | Can do |
|---|---|
| **User** | Manage budgets and reports they have access to; edit their own profile. |
| **Admin** | Everything a User can, plus: invite/remove teammates, edit organisation profile, manage AI integrations and billing. |

"Donor-side approval" isn't a separate role — it's a permission tied to your organisation, not your account. If your organisation is flagged as a donor and is linked as the funder on a budget, any User or Admin in your organisation can confirm that budget and approve/reject reports submitted against it.

> The first person to complete onboarding for a new organisation automatically becomes its Admin — no separate approval step is needed to get started.

---

## 4. Getting Help

Open Grant Flow is open source and under active development — feedback directly shapes what gets built next.

### 4.1 Reporting a problem

The fastest way to report something that isn't working: click the message icon in the top bar, from any page. Describe what you were doing — the page, browser, and time are attached automatically — and optionally attach a screenshot (you can also paste one directly into the description field). The team is notified right away, and you don't need a GitHub account.

### 4.2 Other ways to reach us

- **Source & issues:** [github.com/arutsh/GrantFlow](https://github.com/arutsh/GrantFlow)
- **Contact:** n.arutshyan@gmail.com
- **Website:** [opengrantflow.com](https://opengrantflow.com)
