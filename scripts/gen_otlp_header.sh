#!/usr/bin/env bash
# Usage: ./gen_otlp_header.sh <instance_id> <glc_token>
set -euo pipefail

INSTANCE_ID="${1:?usage: $0 <instance_id> <glc_token>}"
TOKEN="${2:?usage: $0 <instance_id> <glc_token>}"

B64=$(printf '%s' "${INSTANCE_ID}:${TOKEN}" | base64 -w0)
HEADER_VALUE="authorization=Basic ${B64}"

echo "GRAFANA_CLOUD_OTLP_HEADERS value (set this as the GitHub secret):"
echo "${HEADER_VALUE}"
echo
echo "To push it directly:"
echo "  gh secret set GRAFANA_CLOUD_OTLP_HEADERS --body \"${HEADER_VALUE}\""
