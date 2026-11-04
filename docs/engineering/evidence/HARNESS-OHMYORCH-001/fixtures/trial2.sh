#!/bin/bash
# Rehearse the bridged loop on a copy of the working tree, driving hook scripts with synthetic events.
# Fixture evidence only: this does not prove live Claude event delivery or role identity.
set -u
P=/Users/josoroma/sites/autobots
O=$P/research/upstream/OhMyOrch/plugins/ohmyorch
T=$P/.checks/ohmyorch-trial/sandbox2
PY=/opt/homebrew/bin/python3.12
S=sandbox-probe
CH=us-1-1-h0-repository-prerequisite-inventory
omo() { "$O/bin/ohmyorch" --project-root "$T" --session-id "$S" "$@"; }
hook() { # hook <mode> <event> <file> <old> <new>
  jq -nc --arg t "$T" --arg s "$S" --arg ev "$2" --arg f "$T/$3" --arg o "$4" --arg n "$5" \
    '{hook_event_name:$ev,tool_name:"Edit",session_id:$s,cwd:$t,tool_input:{file_path:$f,old_string:$o,new_string:$n},tool_response:{}}' \
    | bash "$O/hooks/dispatch.sh" --project-root "$T" --mode "$1" > hook.out 2>&1
  local rc=$?; echo "hook $1 $3 rc=$rc"; [ "$rc" -eq 0 ] || tail -4 hook.out | cut -c1-180
  return 0
}
edit() { $PY - "$1" "$2" <<'EOF'
import sys
s=open('SPECS.md').read(); assert sys.argv[1].encode().decode('unicode_escape') in s
open('SPECS.md','w').write(s.replace(sys.argv[1].encode().decode('unicode_escape'),sys.argv[2].encode().decode('unicode_escape'),1))
EOF
}

rm -rf "$T"; mkdir -p "$T"
rsync -a --exclude .git --exclude '.env' --exclude '.env.*' --exclude .checks --exclude research/upstream --exclude __pycache__ --exclude .claude/ohmyorch/runtime "$P/" "$T/"
cd "$T" || exit 1
git init -q && git add -A && git -c user.name=probe -c user.email=probe@example.invalid commit -qm base

echo '== doctor'; omo doctor --json | jq -c '{enabled,fails:[.checks[]|select(.status!="PASS")|.name]}'
echo '== start'; omo delivery start EPIC-1 2>&1 | grep -E '^(Action|Story)' | tr '\n' ' '; echo
OLD='### US-1.1: H0 repository and prerequisite inventory\n\nStatus: READY\n'
NEW='### US-1.1: H0 repository and prerequisite inventory\n\nStatus: IN PROGRESS\nChange: `openspec/changes/'$CH'/`\n'

echo '== select, bridged order: SPECS first, while no change is active'
hook pre-write PreToolUse SPECS.md "Status: READY" "Status: IN PROGRESS"
edit "$OLD" "$NEW"; hook post-write PostToolUse SPECS.md a b
$PY scripts/specs.py render | cut -c1-80; $PY scripts/specs.py validate | cut -c1-80
openspec new change "$CH" 2>&1 | tail -1 | cut -c1-90
omo delivery next 2>&1 | grep -E '^(Action|Story|Reason)' | cut -c1-120 | tr '\n' ' '; echo

echo '== negative control: upstream order is rejected once the plan-less change exists'
hook pre-write PreToolUse SPECS.md "x" "y"
hook pre-write PreToolUse scripts/specs.py "x" "y"

echo '== negative control: main session may not author a verdict'
hook pre-write PreToolUse "openspec/changes/$CH/review.md" "x" "y"

echo '== negative control: archive refused before gates pass'
jq -nc --arg t "$T" --arg s "$S" --arg c "openspec archive $CH -y" '{hook_event_name:"PreToolUse",tool_name:"Bash",session_id:$s,cwd:$t,tool_input:{command:$c}}' \
  | bash "$O/hooks/dispatch.sh" --project-root "$T" --mode pre-bash > hook.out 2>&1; echo "archive guard rc=$?"

echo '== stop hook while ACTIVE must block'
jq -nc --arg t "$T" --arg s "$S" '{hook_event_name:"Stop",session_id:$s,cwd:$t,stop_hook_active:false}' \
  | bash "$O/hooks/dispatch.sh" --project-root "$T" --mode stop > hook.out 2>&1; echo "stop rc=$?"; head -3 hook.out | cut -c1-140

echo '== simulate archived US-1.1, then promote (status edits synthetic; no real delivery)'
mkdir -p openspec/changes/archive; mv "openspec/changes/$CH" "openspec/changes/archive/2026-11-04-$CH"
edit 'Status: IN PROGRESS\nChange: `openspec/changes/'$CH'/`\n' 'Status: DONE\nChange: `openspec/changes/archive/2026-11-04-'$CH'/`\n'
$PY - <<'EOF'
s=open('SPECS.md').read(); a=s.index('### US-1.1:'); b=s.index('### US-1.2:')
open('SPECS.md','w').write(s[:a]+s[a:b].replace('- [ ]','- [x]')+s[b:])
EOF
$PY scripts/specs.py render | cut -c1-70
echo '-- before promote:'; omo delivery next 2>&1 | grep -E '^(Action|Story|Reason)' | cut -c1-90 | tr '\n' ' '; echo
$PY scripts/specs.py promote | cut -c1-90; $PY scripts/specs.py validate | cut -c1-80
echo '-- after promote:'; omo delivery next 2>&1 | grep -E '^(Action|Story|Reason)' | cut -c1-90 | tr '\n' ' '; echo
echo '== US-3.4 stays BLOCKED with all deps DONE (external blocker)'
$PY - <<'EOF'
import re
s=open('SPECS.md').read()
b=s[s.index('### US-3.4:'):]; b=b[:b.index('\n### ') if '\n### ' in b else None]
print(re.findall(r'(?m)^- (?:External.*|US-.*)$', b[:b.index('Tasks:')])[:6])
EOF
omo delivery stop 2>&1 | tail -1 | cut -c1-100
echo '== harness in copy'; $PY scripts/verify.py --profile harness > v.out 2>&1; echo "harness rc=$?"
echo '== real repo SPECS untouched'; git -C "$P" diff --stat -- SPECS.md | wc -l
