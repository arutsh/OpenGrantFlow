#!/usr/bin/env bash
# Usage: ./scripts/new-issue.sh "Issue title" "Issue body"
#        ./scripts/new-issue.sh  (interactive prompts)
set -euo pipefail

REPO="arutsh/OpenGrantFlow"
PROJECT_NUMBER=8
PROJECT_OWNER="arutsh"

if [[ $# -ge 1 ]]; then
  TITLE="$1"
else
  read -rp "Title: " TITLE
fi

if [[ $# -ge 2 ]]; then
  BODY="$2"
else
  echo "Body (end with a line containing only '.'):"
  BODY=""
  while IFS= read -r line; do
    [[ "$line" == "." ]] && break
    BODY+="$line"$'\n'
  done
fi

URL=$(gh issue create --repo "$REPO" --title "$TITLE" --body "$BODY")
echo "Created: $URL"

gh project item-add "$PROJECT_NUMBER" --owner "$PROJECT_OWNER" --url "$URL"
echo "Added to project board."
