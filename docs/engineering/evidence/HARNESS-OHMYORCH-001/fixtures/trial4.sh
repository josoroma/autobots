#!/bin/bash
# Fixture rehearsal of the review fixes on a copy of the working tree. Not live delivery evidence.
set -u
P=/Users/josoroma/sites/autobots
O=$P/research/upstream/OhMyOrch/plugins/ohmyorch
T=$P/.checks/ohmyorch-trial/sandbox4
PY=/opt/homebrew/bin/python3.12
S=sandbox-probe
omo() { "$O/bin/ohmyorch" --project-root "$T" --session-id "$S" "$@"; }
pre_specs() {
  jq -nc --arg t "$T" --arg s "$S" --arg f "$T/SPECS.md" --arg o $'### US-1.1: H0 repository and prerequisite inventory\n\nStatus: READY' --arg n $'### US-1.1: H0 repository and prerequisite inventory\n\nStatus: IN PROGRESS' \
    '{hook_event_name:"PreToolUse",tool_name:"Edit",session_id:$s,cwd:$t,tool_input:{file_path:$f,old_string:$o,new_string:$n}}' \
    | bash "$O/hooks/dispatch.sh" --project-root "$T" --mode pre-write > hook.out 2>&1
  echo "$1 rc=$?"; grep -E 'HEAD has moved|BLOCKED' hook.out | head -2 | cut -c1-120
}
fp() { $PY -c "import sys; sys.path.insert(0,'scripts'); from pathlib import Path; from harness_lib import fingerprint; print(fingerprint(Path('.'))[:16])"; }

rm -rf "$T"; mkdir -p "$T"
rsync -a --exclude .git --exclude '.env' --exclude '.env.*' --exclude .checks --exclude research/upstream --exclude __pycache__ --exclude .claude/ohmyorch/runtime --exclude .claude/settings.local.json "$P/" "$T/"
cd "$T" || exit 1
git init -q && git add -A && git -c user.name=probe -c user.email=probe@example.invalid commit -qm base
HEAD0=$(git rev-parse HEAD)

echo '== B1: revision not in this copy is unverifiable, so set it to HEAD first'
sed -i '' "s/^Analyzed revision: .*/Analyzed revision: $HEAD0/" CODEBASE.md
pre_specs 'SPECS edit at recorded HEAD (expect 0)'
echo '-- commit moves HEAD'
git add -A; git -c user.name=probe -c user.email=probe@example.invalid commit -qm story
pre_specs 'SPECS edit after commit (expect 2)'
echo '-- refresh revision, working tree only'
sed -i '' "s/^Analyzed revision: .*/Analyzed revision: $(git rev-parse HEAD)/" CODEBASE.md
pre_specs 'SPECS edit after refresh (expect 0)'

echo '== B2: fingerprint across goal start, refresh and stop-hook state'
A=$(fp); omo delivery start EPIC-1 2>&1 | grep -E '^Action' | cut -c1-40
omo delivery refresh >/dev/null 2>&1
jq -nc --arg t "$T" --arg s "$S" '{hook_event_name:"Stop",session_id:$s,cwd:$t,stop_hook_active:false}' | bash "$O/hooks/dispatch.sh" --project-root "$T" --mode stop >/dev/null 2>&1; echo "stop while ACTIVE rc=$? (expect 2)"
B=$(fp); echo "fingerprint before=$A after=$B"; ls .claude/ohmyorch/runtime 2>/dev/null | head -5 | tr '\n' ' '; echo

echo '== B3: delivery block records the reason and allows stop'
omo delivery block --reason 'fixture: harness verification failed after review and test passed' 2>&1 | tail -1 | cut -c1-120
grep -E '^\| (Status|Reason|Blocked)' openspec/delivery/goal.md | cut -c1-130
jq -nc --arg t "$T" --arg s "$S" '{hook_event_name:"Stop",session_id:$s,cwd:$t,stop_hook_active:false}' | bash "$O/hooks/dispatch.sh" --project-root "$T" --mode stop >hook.out 2>&1; echo "stop after block rc=$? (expect 0)"

echo '== B3: reopen refuses a passing change'
CH=us-1-1-h0-repository-prerequisite-inventory; mkdir -p "openspec/changes/$CH"
omo delivery reopen --change "$CH" 2>&1 | tail -1 | cut -c1-130; rm -rf "openspec/changes/$CH"

echo '== B5: captured list includes untracked files'
echo x > brand-new-file.txt
{ git diff --name-only HEAD; git ls-files --others --exclude-standard; } | sort -u | grep -c brand-new-file.txt
rm -f brand-new-file.txt

echo '== bridge manifest command'
$PY scripts/verify.py --profile harness >/dev/null 2>&1; echo "harness rc=$?"; jq -S .input_manifest .checks/harness/latest.json | jq 'length'

echo '== story_manifest on this copy: capture, compare, then edit a bound file'
M=$P/scripts/story_manifest.py
echo 'product code' > product.py
$PY "$M" capture US-1.1 --project-root . | cut -c1-40; echo "capture rc=${PIPESTATUS[0]}"
$PY "$M" compare US-1.1 --project-root . ; echo "compare rc=$? (expect 0)"
echo 'edited after review' > product.py
$PY "$M" compare US-1.1 --project-root . 2>&1 | cut -c1-80; echo "compare rc=${PIPESTATUS[0]} (expect 1)"
