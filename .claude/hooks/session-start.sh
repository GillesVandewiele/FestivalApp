#!/usr/bin/env bash
# FestivalApp SessionStart hook.
# Injects the harness dispatch skill as additionalContext at session start.
# If the file is missing, start the session without injection rather than failing closed.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
SKILL_FILE="${REPO_ROOT}/.claude/skills/using-festival-harness/SKILL.md"

if [ ! -f "$SKILL_FILE" ]; then
  printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":""}}\n'
  exit 0
fi

escape_for_json() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    s="${s//$'\r'/\\r}"
    s="${s//$'\t'/\\t}"
    printf '%s' "$s"
}

skill_escaped=$(escape_for_json "$(cat "$SKILL_FILE")")
context="<EXTREMELY_IMPORTANT>\nYou are working in the FestivalApp repository. It is PUBLIC on GitHub.\n\n**Below is the full content of your 'using-festival-harness' skill. For all other skills, use the 'Skill' tool:**\n\n${skill_escaped}\n</EXTREMELY_IMPORTANT>"

printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}\n' "$context"
exit 0
