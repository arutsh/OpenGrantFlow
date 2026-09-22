#!/usr/bin/env bash
# Usage: ./scripts/gh-set-secrets.sh [secrets-file]  (default: .env.github-secrets)
set -euo pipefail

REPO="arutsh/OpenGrantFlow"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOW="$REPO_ROOT/.github/workflows/deploy.yml"
SECRETS_FILE="${1:-$REPO_ROOT/.env.github-secrets}"

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI not found: https://cli.github.com/" >&2
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "Not logged in to gh. Run: gh auth login" >&2
  exit 1
fi

if [[ ! -f "$SECRETS_FILE" ]]; then
  echo "Secrets file not found: $SECRETS_FILE" >&2
  echo "Create it (KEY=VALUE per line) — see .env.github-secrets.example — and re-run." >&2
  exit 1
fi

mapfile -t REQUIRED < <(
  { grep -ohP '\$\{\{\s*secrets\.\K[A-Z0-9_]+' "$WORKFLOW"; printf '%s\n' VPS_HOST VPS_USER VPS_SSH_KEY; } | sort -u
)

MISSING=()
TO_SET=()
for name in "${REQUIRED[@]}"; do
  if grep -qE "^${name}=.+" "$SECRETS_FILE"; then
    TO_SET+=("$name")
  else
    MISSING+=("$name")
  fi
done

echo "Target repo: $REPO"
echo "Secrets file: $SECRETS_FILE"
echo

if ((${#MISSING[@]})); then
  echo "Not in $SECRETS_FILE (skipping — existing GitHub values untouched):"
  printf '  - %s\n' "${MISSING[@]}"
  echo
fi

if ((${#TO_SET[@]} == 0)); then
  echo "Nothing to set."
  exit 0
fi

echo "Will set these secrets on $REPO:"
printf '  - %s\n' "${TO_SET[@]}"
read -rp "Proceed? [y/N] " CONFIRM
[[ "$CONFIRM" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 1; }

for name in "${TO_SET[@]}"; do
  value="$(grep -E "^${name}=.+" "$SECRETS_FILE" | head -1 | cut -d= -f2-)"
  value="${value%\"}"
  value="${value#\"}"
  gh secret set "$name" --repo "$REPO" --body "$value"
  echo "Set $name"
done

echo "Done."
