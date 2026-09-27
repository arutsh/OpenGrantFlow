# GrantFlow Deployment Modes

GrantFlow supports three deployment modes to suit different use cases and deployment targets:

## 1. 🚀 DEV MODE (Development)

**Use case:** Local development with hot-reload capabilities.

**What runs:**
- ✅ PostgreSQL (Docker)
- ✅ Redis (Docker)
- ✅ API Gateway (Docker)
- ✅ Nginx Proxy (Docker)
- ❌ Frontend (runs locally)
- ❌ Users Service (runs locally)
- ❌ Budget Service (runs locally)

**Benefits:**
- Hot-reload for backend code changes
- Frontend assets compiled in real-time
- Faster local development iteration
- Reduced Docker container overhead

### Quick Start

```bash
# Start infrastructure
./dev.sh up

# In separate terminals, start local services:
cd services/users && python -m uvicorn main:app --reload
cd services/budget && python -m uvicorn main:app --reload
cd frontend-typescript && npm run dev
```

### Available Commands

```bash
./dev.sh up           # Start infrastructure
./dev.sh down         # Stop infrastructure
./dev.sh logs         # View logs
./dev.sh status       # Show container status
./dev.sh rebuild      # Rebuild containers without cache
./dev.sh clean        # Stop and remove volumes
```

### Endpoints (Dev Mode)

| Service | URL |
|---------|-----|
| Database | localhost:5432 |
| Redis | localhost:6379 |
| API Gateway | http://localhost:8080 |
| Nginx Proxy | http://localhost:8082 |
| Users Service | http://localhost:8000 |
| Budget Service | http://localhost:8001 |
| Frontend | http://localhost:3000 |

---

## 2. 🏠 LOCAL MODE (Production-like Local)

**Use case:** Complete local testing, demo for non-technical users, CI/CD testing.

**What runs:**
- ✅ PostgreSQL (Docker)
- ✅ Redis (Docker)
- ✅ API Gateway (Docker)
- ✅ Nginx Proxy (Docker)
- ✅ Frontend (Docker)
- ✅ Users Service (Docker)
- ✅ Budget Service (Docker)

**Benefits:**
- Everything runs in Docker
- No local dependencies required
- Production-like environment
- Perfect for demos and non-technical users
- Easy to share and reproduce

### Quick Start

```bash
# Start everything
./local.sh up

# Open browser
open http://localhost:3000
```

### Available Commands

```bash
./local.sh up              # Start all services
./local.sh down            # Stop all services
./local.sh logs [SERVICE]  # View logs (optional: specific service)
./local.sh status          # Show container status
./local.sh rebuild         # Rebuild containers without cache
./local.sh clean           # Stop and remove volumes
./local.sh shell [SERVICE] # Open shell in container
```

### Endpoints (Local Mode)

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Nginx Proxy | http://localhost:8082 |
| API Gateway | http://localhost:8080 |
| Users Service | http://localhost:8000 |
| Budget Service | http://localhost:8001 |
| Database | localhost:5432 |

### Database Access (Local Mode)

```
Host: localhost
Port: 5432
User: postgres
Password: postgres
Databases: 
  - grantflow_users
  - grantflow_budget
```

---

## 3. ☁️ CLOUD MODE (SaaS - Future)

**Use case:** Scalable cloud deployment (AWS, Azure, GCP, etc.).

**What runs:**
- Kubernetes or orchestration platform
- Managed databases
- Load-balanced services
- Auto-scaling replicas
- CDN & monitoring

**Status:** 🚧 Under development

### Show Architecture Info

```bash
./cloud.sh info
```

### Future Implementation

The codebase is designed to support cloud deployment:
- ✅ Environment-based configuration
- ✅ Health checks implemented
- ✅ Stateless services
- ✅ Database migrations automated
- 🔄 Kubernetes manifests (TODO)
- 🔄 CI/CD pipelines (TODO)
- 🔄 Infrastructure-as-Code (TODO)

---

## 4. 🖥️ PRODUCTION MODE (Hetzner Cloud, Terraform-provisioned)

**Use case:** Real production deployment. Backend runs on a Hetzner Cloud server; frontend is hosted separately on Vercel.

**What runs:**
- ✅ PostgreSQL, Redis, RabbitMQ (Docker)
- ✅ Users, Budget, AI services (Docker)
- ✅ Celery worker + beat (Docker)
- ✅ Caddy (Docker) — reverse proxy + automatic Let's Encrypt TLS for `api.opengrantflow.com`
- ❌ Frontend (hosted on Vercel, not part of this stack)

Compose file: `docker-compose.prod.yml`. Reverse proxy config: `Caddyfile`. Server provisioning: `terraform/`.

> **History:** this originally ran on a manually-ordered OVH classic VPS, bootstrapped by hand over SSH (see git history for that flow if you ever need it). It was migrated to Hetzner Cloud because that product line is API-first — Terraform can genuinely own the server/firewall/SSH-key lifecycle, which a classic VPS storefront doesn't expose. The app-level pieces (`docker-compose.prod.yml`, `Caddyfile`, `.github/workflows/deploy.yml`) needed **zero changes** for the migration — only the provisioning layer changed.

### One-time server provisioning (Terraform)

Unlike the old OVH flow, there's no manual SSH bootstrap at all — Terraform creates the server with a cloud-init script attached, which does everything (deploy user, Docker install, repo clone) on first boot.

```bash
cd terraform/
cp terraform.tfvars.example terraform.tfvars   # fill in your Hetzner API token (gitignored)
terraform init
terraform plan     # review: should show 3 resources (ssh_key, firewall, server)
terraform apply    # type "yes" when prompted — creates real, billable infra
```

Wait ~1-2 minutes after `apply` completes for cloud-init to finish (Docker install + repo clone happen in the background after the server is reported "created"), then verify:

```bash
ssh -i <path-to-deploy-private-key> deploy@$(terraform output -raw server_ipv4) "docker ps && ls /opt/grandflow"
```
Should log in with no password prompt, show an empty container list, and the cloned repo.

**Firewall**: managed by Terraform (`hcloud_firewall` in `terraform/main.tf`), not `ufw` — 80/443 open to everyone, 22 also open to everyone (the GitHub Actions deploy workflow needs to reach it from an unpredictable runner IP; SSH key-only auth, not IP restriction, is the actual security boundary here).

**Terraform state** is local (gitignored `terraform.tfstate`) — there is no built-in history/changelog for local state, only the current state plus one automatic backup file. A remote backend (e.g. Terraform Cloud) is a noted future upgrade if a real audit trail becomes worth it.

### DNS

Add an A record at your registrar: `api.opengrantflow.com` → the `server_ipv4` output from `terraform apply`. Give it a few minutes to propagate before the first deploy, since Caddy requests a Let's Encrypt cert on first boot and needs the domain to already resolve.

### GitHub Actions secrets required

All set already: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `RABBITMQ_USER`, `RABBITMQ_PASS`, `RABBITMQ_URL`, `USERS_DATABASE_URL`, `BUDGET_DATABASE_URL`, `AI_DATABASE_URL`, `JWT_SECRET_KEY`, `ENCRYPTION_KEY`, `VPS_USER` (`deploy`), `VPS_SSH_KEY` (private half of the deploy keypair — the same keypair Terraform registers as `hcloud_ssh_key`, reused rather than regenerated), `GRAFANA_CLOUD_OTLP_ENDPOINT`, `GRAFANA_CLOUD_OTLP_HEADERS` (see Observability below). `VPS_HOST` needs updating any time the server is recreated (`terraform destroy && terraform apply` would produce a new IP) — set it to the current `server_ipv4` output.

`INTERNAL_SERVICE_TOKEN` (shared secret budget/ai/chat send to users for internal batch lookups, see `shared/security/internal_service.py`) is new and still needs to be set — generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"`.

**Not yet set — needed for the platform-funded AI fallback (`services/ai`):** `ANTHROPIC_API_KEY`. Without it, `resolve_platform_funded_model()` returns `None` and every platform-funded fallback path (excel import for zero-key orgs, and the superuser-gated `/ai/decide` / `/ai/parse-budget/stream` fallback) fails closed even when it should recover — confirmed missing in prod on 2026-08-25.

### Observability

Traces, metrics, and logs from all five services (the four FastAPI services
plus `worker`) export via OTLP straight to a hosted Grafana Cloud free-tier
stack — no monitoring containers on the prod box. See
[`docs/observability/GRAFANA_CLOUD_PRODUCTION.md`](../observability/GRAFANA_CLOUD_PRODUCTION.md)
for how it's wired, where to view traces/dashboards/logs, and the
`OTEL_SDK_DISABLED=true` rollback flag.

**Not yet set — needed for email verification (`services/worker`):** `MAILERSEND_API_TOKEN`, `MAILERSEND_SENDER_DOMAIN`, `MAILERSEND_SENDER_EMAIL`, `FRONTEND_BASE_URL`. `MAILJET_API_KEY`, `MAILJET_SECRET_KEY`, `MAILJET_SENDER_EMAIL` are also plumbed through but not required until `EMAIL_PROVIDER` is flipped to `mailjet` in prod. See the "Email verification (MailerSend / Mailjet)" section below for what each one is. Without the active provider's vars set, `deploy.yml`'s `envsubst` step leaves the `${VAR}` placeholders in `services/worker/.env.worker.prod` unexpanded, so the worker sends with empty credentials.

### Ongoing deploys

Every push to `main` triggers `.github/workflows/deploy.yml`, which SSHes in, resets the checkout to `origin/main`, regenerates the real `.env.prod` / `services/*/.env.*.prod` files in place from the secrets above (the committed versions are `${VAR}` templates, never real values), and runs:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

Manual redeploy (e.g. to pick up a secret rotation without a new commit): re-run the workflow from the Actions tab (`workflow_dispatch`).

---

## Switching Between Modes

### Dev → Local

```bash
# Stop dev infrastructure
./dev.sh down

# Start local mode
./local.sh up
```

### Local → Dev

```bash
# Stop local stack
./local.sh down

# Start dev infrastructure
./dev.sh up
```

---

## Performance & Caching

All modes use Docker BuildKit with persistent cache mounts for faster builds:

```bash
DOCKER_BUILDKIT=1 docker compose build
```

**Benefits:**
- Python packages cached between builds
- No re-downloading of pip dependencies
- Builds ~10x faster on subsequent runs

---

## Troubleshooting

### Services won't start (Dev Mode)

**Problem:** Services exit immediately

**Solution:**
```bash
# Check logs
./dev.sh logs

# Make sure DB is healthy
docker compose -f docker-compose.dev.yml exec grantflow-db pg_isready
```

### Port already in use

**Solution:**
```bash
# Find service using port
lsof -i :8000

# Or use different dev file
docker compose -f docker-compose.dev.yml down
```

### Rebuild without cache

All modes support clean rebuild:

```bash
# Dev mode
./dev.sh rebuild

# Local mode
./local.sh rebuild
```

### Reset everything

```bash
# Dev mode
./dev.sh clean

# Local mode
./local.sh clean
```

---

## Default Environment Files

Each mode uses environment files for configuration:

- **Dev Mode:** `.env.*.dev` files
- **Local Mode:** `.env.*.dev` files
- **Production Mode:** `.env.prod` / `.env.*.prod` files — committed as `${VAR}` templates, real values generated in place on the server from GitHub Actions secrets at deploy time (see section 4)
- **Cloud Mode:** To be defined per cloud provider

Example:
```
./services/users/.env.users.dev
./services/budget/.env.budget.private.dev
./api-gateway/.env.gateway.dev
```

### Email verification (MailerSend / Mailjet)

`services/worker` sends the registration confirmation email through a provider-agnostic interface (`shared/services/email_provider.py`); which vendor actually sends it is a runtime config choice, not a code change. `EMAIL_PROVIDER` (in `services/worker/.env.worker.*`) selects the active client:

| Value | Behavior |
|-------|----------|
| `mailersend` (default, or unset) | Sends via [MailerSend's Email API](https://developers.mailersend.com/api/v1/email.html). |
| `mailjet` | Sends via [Mailjet's Send API v3.1](https://dev.mailjet.com/email/guides/send-api-v31/). |

Any other value raises a configuration error at worker startup rather than silently falling back — a typo in `EMAIL_PROVIDER` fails loud instead of reverting to whichever provider was previously active.

**MailerSend config:**

| Var | Purpose |
|-----|---------|
| `MAILERSEND_API_TOKEN` | MailerSend account API token (Email API). |
| `MAILERSEND_SENDER_DOMAIN` | Trial domain in dev/local (capped at 100 sends, only delivers to recipients verified on the account); a verified sending domain in production. |
| `MAILERSEND_SENDER_EMAIL` | The `from` address on outgoing mail — must belong to `MAILERSEND_SENDER_DOMAIN`. |
| `MAILERSEND_SENDER_NAME` | Display name on outgoing mail. Defaults to `GrandFlow`. |
| `MAILERSEND_VERIFICATION_TEMPLATE_ID` | MailerSend dashboard template ID for the verification email. |
| `MAILERSEND_PASSWORD_RESET_TEMPLATE_ID` | MailerSend dashboard template ID for the password-reset email. |
| `MAILERSEND_API_URL` | Optional override for the Email API endpoint. Leave blank to use the real MailerSend API — only set this to redirect sends at a local mock server instead. |

**Mailjet config:**

| Var | Purpose |
|-----|---------|
| `MAILJET_API_KEY` / `MAILJET_SECRET_KEY` | Mailjet Send API v3.1 credentials — HTTP Basic Auth (key + secret), not a bearer token. |
| `MAILJET_SENDER_EMAIL` | The `from` address on outgoing mail — must belong to a verified Mailjet sender. |
| `MAILJET_SENDER_NAME` | Display name on outgoing mail. Defaults to `GrandFlow`. |
| `MAILJET_VERIFICATION_TEMPLATE_ID` | Mailjet dashboard template ID for the verification email. |
| `MAILJET_PASSWORD_RESET_TEMPLATE_ID` | Mailjet dashboard template ID for the password-reset email. |
| `MAILJET_API_URL` | Optional override for the Send API endpoint. Leave blank to use the real Mailjet API — only set this to redirect sends at a local mock server instead. |

Shared across both: `FRONTEND_BASE_URL` — origin used to build the `/verify-email?token=...` link in the email (e.g. `http://localhost:3000` in dev, the deployed frontend origin in prod).

Real credentials are never committed — `MAILERSEND_API_TOKEN`/`MAILERSEND_SENDER_DOMAIN`/`MAILERSEND_SENDER_EMAIL` and `MAILJET_API_KEY`/`MAILJET_SECRET_KEY`/`MAILJET_SENDER_EMAIL` are left blank in the committed `.env.worker.dev`/`.env.worker.local` templates; fill them in locally to actually send mail. Without them, registration still succeeds but the confirmation email enqueue will fail at send time (retried with backoff, self-serviceable via `POST /auth/resend-verification`).

`.env.worker.dev`/`.env.worker.local` ship with `EMAIL_PROVIDER=mailjet` so local/dev testing isn't blocked by MailerSend's trial-recipient cap (see below). Prod stays on `mailersend` (or unset) until Mailjet is validated in dev.

**Trial-domain recipient allowlist (MailerSend):** on a free-tier account, `POST /v1/email` only delivers to recipient addresses explicitly added and verified in the MailerSend dashboard (Domains → trial domain → recipients), capped at 100 sends total. Sending to any other address — real or made-up — is rejected at the API level, not silently dropped. In practice: either register with your own verified address while testing, or pre-verify a small set of test addresses in the dashboard. This cap is the reason Mailjet was added as a second provider and is the default in dev/local.

**No sandbox mode (Mailjet):** unlike MailerSend, Mailjet has no separate sandbox/test API — dev, local, and prod all hit the same live Send API with real credentials, distinguished only by which `MAILJET_*` values and `EMAIL_PROVIDER` setting are active in each environment's env file. There's no trial-recipient cap to work around, but it also means dev/local sends via Mailjet are real emails through a real account, not a sandboxed no-op.

**Rolling back:** unset `EMAIL_PROVIDER`, or set it back to `mailersend`, in the relevant `.env.worker.*` file (and, in prod, the corresponding GitHub Actions secret substitution). No data migration is involved — the switch is config-only and fully reversible.

**If MailerSend becomes primary again:** the code sends a `privacy_url` personalization var to both providers, but only the Mailjet dashboard templates were edited to render it as a footer link (`high-privacy-policy-mailjet-compliance`, task 2.5) — the MailerSend templates were left untouched (task 2.6, deliberately skipped since MailerSend wasn't the active provider). Revisit both `MAILERSEND_VERIFICATION_TEMPLATE_ID` and `MAILERSEND_INVITE_TEMPLATE_ID` templates in the MailerSend dashboard and add the same link before flipping `EMAIL_PROVIDER` back.

---

## Architecture Comparison

| Feature | Dev | Local | Cloud |
|---------|-----|-------|-------|
| Hot-reload | ✅ | ❌ | ❌ |
| Docker only | ❌ | ✅ | ✅* |
| Local deps | ✅ | ❌ | ❌ |
| Scale-ready | ❌ | ❌ | ✅ |
| Non-tech user | ❌ | ✅ | ✅ |
| Dev speed | ⚡⚡ | ⚡ | 🔄 |

*Cloud mode requires cloud provider setup

---

## For Maintainers

### Modifying Docker Compose Files

1. **Dev mode:** `docker-compose.dev.yml`
2. **Local mode:** `docker-compose.local.yml`
3. **Cloud mode:** Define `docker-compose.cloud.yml` or K8s manifests

### Adding New Services

If adding a new service:
1. Add to `docker-compose.dev.yml` for dev testing
2. Add to `docker-compose.local.yml` for production-like local
3. Keep services stateless for cloud portability

### Environment Variables

Use `env_file` directive in compose files:
```yaml
env_file:
  - ./services/users/.env.users.dev
```

Keep `.env` files in `.gitignore` and provide `.env.example` templates.

---

## Quick Reference

```bash
# Start developing
./dev.sh up

# Run services locally (in separate terminals)
cd services/users && python -m uvicorn main:app --reload
cd services/budget && python -m uvicorn main:app --reload
cd frontend-typescript && npm run dev

# Test local mode
./local.sh up

# Check cloud readiness
./cloud.sh info
```
