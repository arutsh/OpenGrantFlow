#!/usr/bin/env bash
# Usage: ./scripts/start-group.sh <change-name> <group-number> - see docs/development/WORKFLOW.md
set -euo pipefail

REPO="arutsh/OpenGrantFlow"
PROJECT_NUMBER=8
PROJECT_OWNER="arutsh"
PROJECT_ID="PVT_kwHOAQDyGs4A-5Lx"
STATUS_FIELD_ID="PVTSSF_lAHOAQDyGs4A-5LxzgyKO-Q"
STATUS_IN_PROGRESS="47fc9ee4"

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <change-name> <group-number>" >&2
  exit 1
fi

CHANGE="$1"
GROUP="$2"

TASKS_FILE="openspec/changes/${CHANGE}/tasks.md"

if [[ ! -f "$TASKS_FILE" ]]; then
  echo "error: $TASKS_FILE not found" >&2
  exit 1
fi

if [[ ! "$CHANGE" =~ ^([a-z]+)-(feat|fix|chore|refactor)-([0-9]+)-(.+)$ ]]; then
  echo "error: change name '$CHANGE' doesn't match <service>-<type>-<issue>-<description>" >&2
  echo "       type must be one of feat/fix/chore/refactor, issue must be numeric" >&2
  exit 1
fi

SERVICE_RAW="${BASH_REMATCH[1]}"
TYPE="${BASH_REMATCH[2]}"
PARENT_ISSUE="${BASH_REMATCH[3]}"
DESC="${BASH_REMATCH[4]}"

GROUP_LINE_NUM=$(grep -nE "^## ${GROUP}\." "$TASKS_FILE" | head -1 | cut -d: -f1)
if [[ -z "$GROUP_LINE_NUM" ]]; then
  echo "error: no '## ${GROUP}.' group header found in $TASKS_FILE" >&2
  exit 1
fi
GROUP_LINE=$(sed -n "${GROUP_LINE_NUM}p" "$TASKS_FILE")

case "$SERVICE_RAW" in
  ai) SERVICE="AI" ;;
  backend) SERVICE="Backend" ;;
  budget) SERVICE="Budget" ;;
  chat) SERVICE="Chat" ;;
  feature) SERVICE="Feature" ;;
  frontend) SERVICE="Frontend" ;;
  platform) SERVICE="Platform" ;;
  shared) SERVICE="Shared" ;;
  users) SERVICE="Users" ;;
  *)
    echo "error: unknown service '$SERVICE_RAW' - add it to the case map in $0" >&2
    exit 1
    ;;
esac

# Group header carries its own sub-issue once created: "## N. Title — Issue #123"
if [[ "$GROUP_LINE" =~ Issue\ \#([0-9]+) ]]; then
  SUB_ISSUE="${BASH_REMATCH[1]}"
  GROUP_TITLE=$(sed -E "s/^## ${GROUP}\. //; s/ — Issue #[0-9]+\$//" <<< "$GROUP_LINE")
  echo "Reusing existing sub-issue #${SUB_ISSUE} for group ${GROUP}"
else
  GROUP_TITLE=$(sed -E "s/^## ${GROUP}\. //" <<< "$GROUP_LINE")
  SUB_TITLE="${DESC}: ${GROUP_TITLE} (group ${GROUP})"
  SUB_BODY="Part of #${PARENT_ISSUE} (\`${CHANGE}\` OpenSpec change). See openspec/changes/${CHANGE}/tasks.md, group ${GROUP}."

  SUB_URL=$(gh issue create --repo "$REPO" --title "$SUB_TITLE" --body "$SUB_BODY")
  SUB_ISSUE="${SUB_URL##*/}"
  echo "Created sub-issue #${SUB_ISSUE}: ${SUB_TITLE}"

  gh project item-add "$PROJECT_NUMBER" --owner "$PROJECT_OWNER" --url "$SUB_URL" >/dev/null
  echo "Added #${SUB_ISSUE} to project board"

  PARENT_DB_ID=$(gh api "repos/${REPO}/issues/${PARENT_ISSUE}" --jq .id)
  SUB_DB_ID=$(gh api "repos/${REPO}/issues/${SUB_ISSUE}" --jq .id)
  gh api "repos/${REPO}/issues/${PARENT_ISSUE}/sub_issues" --method POST -F "sub_issue_id=${SUB_DB_ID}" >/dev/null
  echo "Linked #${SUB_ISSUE} as a sub-issue of #${PARENT_ISSUE}"

  sed -i "${GROUP_LINE_NUM}s/\$/ — Issue #${SUB_ISSUE}/" "$TASKS_FILE"
  echo "Recorded Issue #${SUB_ISSUE} on group ${GROUP}'s header in $TASKS_FILE"
fi

BRANCH="${SERVICE}/${TYPE}/Issue-${SUB_ISSUE}/${DESC}-group${GROUP}"

echo
echo "Change:  $CHANGE"
echo "Group:   ${GROUP}. ${GROUP_TITLE}"
echo "Parent:  #${PARENT_ISSUE}"
echo "Sub-issue: #${SUB_ISSUE}"
echo "Branch:  ${BRANCH}"
echo

if git show-ref --verify --quiet "refs/heads/${BRANCH}"; then
  echo "error: branch ${BRANCH} already exists" >&2
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "error: working tree not clean - commit or stash before starting a new group" >&2
  exit 1
fi

git fetch origin main
git checkout main
git pull --ff-only origin main
git checkout -b "$BRANCH"

echo "Created and checked out $BRANCH"

ITEM_ID=$(gh project item-list "$PROJECT_NUMBER" --owner "$PROJECT_OWNER" --limit 200 --format json \
  | jq -r --argjson issue "$SUB_ISSUE" '.items[] | select(.content.number == $issue) | .id')

if [[ -z "$ITEM_ID" ]]; then
  echo "warning: no project item found for issue #${SUB_ISSUE}; skipping status update" >&2
else
  gh project item-edit --id "$ITEM_ID" --project-id "$PROJECT_ID" \
    --field-id "$STATUS_FIELD_ID" --single-select-option-id "$STATUS_IN_PROGRESS"
  echo "Set project item for issue #${SUB_ISSUE} to In Progress"
fi

echo
echo "Next: implement group ${GROUP}, then open a PR with 'Closes #${SUB_ISSUE}'."
echo "Once every sub-issue of #${PARENT_ISSUE} is closed, close #${PARENT_ISSUE} too."
