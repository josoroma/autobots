#!/bin/bash
# Fixture recheck on sandbox2: a unique-string select edit passes; a premature DONE is refused.
set -u
P=/Users/josoroma/sites/autobots
O=$P/research/upstream/OhMyOrch/plugins/ohmyorch
T=$P/.checks/ohmyorch-trial/sandbox2
S=sandbox-probe
cd "$T" || exit 1
"$O/bin/ohmyorch" --project-root "$T" --session-id "$S" delivery start EPIC-1 2>&1 | grep -E '^(Action|Story)' | tr '\n' ' '; echo
echo "active changes: $(find openspec/changes -maxdepth 1 -mindepth 1 -type d -not -name archive | wc -l)"
hook() { # hook <label> <old> <new>
  jq -nc --arg t "$T" --arg s "$S" --arg f "$T/SPECS.md" --arg o "$2" --arg n "$3" \
    '{hook_event_name:"PreToolUse",tool_name:"Edit",session_id:$s,cwd:$t,tool_input:{file_path:$f,old_string:$o,new_string:$n}}' \
    | bash "$O/hooks/dispatch.sh" --project-root "$T" --mode pre-write > hook.out 2>&1
  echo "$1 rc=$?"; head -3 hook.out | cut -c1-170
}
H12=$'### US-1.2: H0 shared instructions and development assistant assets\n\nStatus: READY'
hook 'select US-1.2 with unique old_string (expect 0)' "$H12" $'### US-1.2: H0 shared instructions and development assistant assets\n\nStatus: IN PROGRESS\nChange: `openspec/changes/us-1-2-h0-shared-instructions-development/`'
hook 'premature DONE on US-1.2 (expect refusal)' "$H12" $'### US-1.2: H0 shared instructions and development assistant assets\n\nStatus: DONE'
"$O/bin/ohmyorch" --project-root "$T" --session-id "$S" delivery stop 2>&1 | tail -1 | cut -c1-80
