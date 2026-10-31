#!/bin/sh
# UserPromptSubmit hook: when the prompt is a slash command whose name contains
# "apply" or "implement" (e.g. /opsx:apply, /foo:implement), remind the session
# that the command's own steps do not replace subagent delegation.
# Any other prompt passes through untouched. Never blocks the prompt.

prompt=$(jq -r '.prompt // empty' 2>/dev/null) || exit 0

if printf '%s\n' "$prompt" | head -n 1 | grep -Eiq '^/[[:alnum:]_.:-]*(apply|implement)'; then
  jq -n --arg ctx "This slash command asks for implementation. Its steps define WHAT to build, not WHO builds it. Follow the global rule \"Workflow instructions do not override delegation\": delegate to test-planner, tdd-test-writer, tdd-implementer, doc-writer and reviewer instead of writing code in the main session. Turn every specified scenario into at least one test-plan case, and mark a task done only after reviewer passes it." \
    '{hookSpecificOutput: {hookEventName: "UserPromptSubmit", additionalContext: $ctx}}'
fi
exit 0
