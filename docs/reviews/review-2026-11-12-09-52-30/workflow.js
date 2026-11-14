export const meta = {
  name: 'code-quality-review',
  description: 'Review code quality and maintainability, then write verified findings, standards and a refactor plan to docs/reviews/review-<timestamp>',
  whenToUse: 'A repository-wide review of standards, modules, size, functions, structure, approaches, comments, types and maintainability. Optional args: {"timestamp": "yyyy-mm-dd-hh-mm-ss"} (default: the current time); {"timestamp": "...", "resume": true} continues a stopped run from what it left on disk; "notes": ["..."] adds lines to the run facts.',
  phases: [
    { title: 'Measure', detail: 'size, complexity and lint metrics from the installed tools' },
    { title: 'Review', detail: 'one reviewer per area and per cross-cutting lens' },
    { title: 'Verify', detail: 'adversarial check of every finding, which writes the findings files' },
    { title: 'Synthesize', detail: 'standards, refactor plan and README' },
    { title: 'Check', detail: 'links, finding IDs and coverage' },
  ],
}

// docs/reviews/PROMPT.md holds the rules, rubrics and output formats, and every agent reads it.
// This script decides the areas, who reads what, and the order. Keep the two in step.
// Agent count: 1 measure + 26 reviewers + 14 verifiers + 3 writers + 1 checker = 45 when nothing
// fails. An agent that returns nothing gets one retry, which adds one agent each time.
const PROMPT_FILE = 'docs/reviews/PROMPT.md'
const WORKFLOW_FILE = '.claude/workflows/code-quality-review.js'

const DIMENSIONS = ['standards', 'modules', 'size', 'functions', 'structure', 'approach', 'comments', 'types', 'errors', 'tests', 'duplication', 'naming']
const SCORE_DIMENSIONS = ['standards', 'modules', 'size', 'functions', 'structure', 'approach', 'comments', 'types', 'errors', 'tests', 'maintainability']
const SEVERITIES = ['high', 'medium', 'low']

// ---------------------------------------------------------------- schemas

const LOCATION = {
  type: 'object',
  properties: {
    file: { type: 'string', description: 'Repository-relative path' },
    line: { type: 'integer', minimum: 1 },
    endLine: { type: 'integer', minimum: 1 },
    note: { type: 'string' },
  },
  required: ['file', 'line'],
}

const FINDING = {
  type: 'object',
  properties: {
    title: { type: 'string' },
    dimension: { type: 'string', enum: DIMENSIONS },
    severity: { type: 'string', enum: SEVERITIES },
    locations: { type: 'array', items: LOCATION, minItems: 1, maxItems: 8 },
    occurrences: { type: 'integer', minimum: 1, description: 'Total places that show this; 1 for a single instance' },
    evidence: { type: 'string', description: 'What the code does now. An excerpt of at most eight lines is allowed' },
    impact: { type: 'string', description: 'Why it matters here: change cost, defect risk or confusion' },
    recommendation: { type: 'string' },
    sketch: { type: 'string', description: 'Target shape. Required for high and size findings; may be empty otherwise' },
    effort: { type: 'string', enum: ['S', 'M', 'L'] },
    risk: { type: 'string', enum: ['low', 'medium', 'high'] },
    ruleCheck: { type: 'string', description: 'The project rule or decision this touches and how the recommendation stays within it, or "none"' },
  },
  required: ['title', 'dimension', 'severity', 'locations', 'occurrences', 'evidence', 'impact', 'recommendation', 'sketch', 'effort', 'risk', 'ruleCheck'],
}

const REVIEW_SCHEMA = {
  type: 'object',
  properties: {
    summary: { type: 'string' },
    scores: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          dimension: { type: 'string', enum: SCORE_DIMENSIONS },
          score: { type: 'integer', minimum: 1, maximum: 5 },
          why: { type: 'string' },
        },
        required: ['dimension', 'score', 'why'],
      },
    },
    strengths: {
      type: 'array',
      items: { type: 'object', properties: { title: { type: 'string' }, evidence: { type: 'string' } }, required: ['title', 'evidence'] },
    },
    findings: { type: 'array', items: FINDING, maxItems: 25 },
    filesRead: { type: 'array', items: { type: 'string' } },
    notCovered: { type: 'string' },
  },
  required: ['summary', 'scores', 'strengths', 'findings', 'filesRead', 'notCovered'],
}

const MEASURE_SCHEMA = {
  type: 'object',
  properties: {
    stop: { type: 'string', description: 'Empty, or the reason the run must stop' },
    timestamp: { type: 'string' },
    outDir: { type: 'string' },
    rawDir: { type: 'string' },
    revision: { type: 'string' },
    dirtyFiles: { type: 'integer', minimum: 0 },
    files: { type: 'array', items: { type: 'string' } },
    fileMetrics: {
      type: 'array',
      items: {
        type: 'object',
        properties: { file: { type: 'string' }, loc: { type: 'integer' }, notes: { type: 'string' } },
        required: ['file', 'loc', 'notes'],
      },
    },
    toolProblems: { type: 'string', description: 'Commands that failed or were refused, or empty' },
    summary: { type: 'string', description: 'The ten numbers that matter most, one per line' },
  },
  required: ['stop', 'timestamp', 'outDir', 'rawDir', 'revision', 'dirtyFiles', 'files', 'fileMetrics', 'toolProblems', 'summary'],
}

// What a resumed run finds on disk for one area or lens.
const PART_STATE = {
  type: 'object',
  properties: {
    key: { type: 'string' },
    verified: { type: 'boolean', description: 'Both findings files exist and the JSON parses' },
    savedReview: { type: 'string', description: 'Path of a saved review that parses, or empty' },
    high: { type: 'integer', minimum: 0 },
    medium: { type: 'integer', minimum: 0 },
    low: { type: 'integer', minimum: 0 },
    rejected: { type: 'integer', minimum: 0 },
    notCovered: { type: 'string' },
  },
  required: ['key', 'verified', 'savedReview', 'high', 'medium', 'low', 'rejected', 'notCovered'],
}

const INVENTORY_SCHEMA = {
  type: 'object',
  properties: {
    stop: { type: 'string' },
    timestamp: { type: 'string' },
    outDir: { type: 'string' },
    rawDir: { type: 'string' },
    revision: { type: 'string' },
    dirtyFiles: { type: 'integer', minimum: 0 },
    files: { type: 'array', items: { type: 'string' } },
    toolProblems: { type: 'string' },
    parts: { type: 'array', items: PART_STATE },
  },
  required: ['stop', 'timestamp', 'outDir', 'rawDir', 'revision', 'dirtyFiles', 'files', 'toolProblems', 'parts'],
}

const VERIFY_SCHEMA = {
  type: 'object',
  properties: {
    areas: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          key: { type: 'string' },
          kept: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                id: { type: 'string' },
                severity: { type: 'string', enum: SEVERITIES },
                dimension: { type: 'string' },
                title: { type: 'string' },
                verdict: { type: 'string', enum: ['confirmed', 'revised'] },
              },
              required: ['id', 'severity', 'dimension', 'title', 'verdict'],
            },
          },
          rejected: {
            type: 'array',
            items: { type: 'object', properties: { id: { type: 'string' }, reason: { type: 'string' } }, required: ['id', 'reason'] },
          },
          filesWritten: { type: 'array', items: { type: 'string' } },
        },
        required: ['key', 'kept', 'rejected', 'filesWritten'],
      },
    },
  },
  required: ['areas'],
}

const CHECK_SCHEMA = {
  type: 'object',
  properties: {
    fixed: { type: 'array', items: { type: 'string' } },
    remaining: { type: 'array', items: { type: 'string' } },
  },
  required: ['fixed', 'remaining'],
}

// ---------------------------------------------------------------- measurement commands
// String.raw keeps backslashes for grep, tr and Python. These blocks hold no backticks and no
// dollar-brace sequences, because either would end or interpolate the template.
// __TS__ is the requested timestamp (may be empty); __RUN_TS__ is the timestamp step 1 settles.

const MEASURE_SETUP = String.raw`TS=__TS__
[ -n "$TS" ] || TS=$(date +%Y-%m-%d-%H-%M-%S)
OUT=docs/reviews/review-$TS; RAW=.checks/reviews/review-$TS
if [ -d "$OUT" ] && [ -n "$(ls -A "$OUT")" ]; then echo "STOP: $OUT already holds files. To continue that run, start the workflow again with the same timestamp and resume set to true."; exit 0; fi
mkdir -p "$OUT/findings" "$RAW" && echo "TS=$TS"
git rev-parse HEAD
git status --porcelain | wc -l
services/agent/.venv/bin/ruff --version; python3.12 --version
"$HOME/.nvm/versions/node/v$(cat .node-version)/bin/node" --version
(cd apps/web && PATH="$HOME/.nvm/versions/node/v$(cat ../../.node-version)/bin:$PATH" node_modules/.bin/eslint --version)`

const MEASURE_FILES = String.raw`TS=__RUN_TS__; RAW=.checks/reviews/review-$TS
git ls-files | grep -E '\.(ts|tsx|mjs|js|py|sql|sh|css)$|Dockerfile|Makefile$|compose[^/]*\.ya?ml$|(^|/)(package\.json|tsconfig\.json|pyproject\.toml)$' \
  | grep -v -E '^(openspec|docs|research)/|^packages/api-client/src/generated\.ts$|^packages/db-types/src/generated\.ts$|^contracts/generated/|^infra/supabase/upstream/|^\.claude/(worktrees|ohmyorch|workflows|skills|agents|rules)/' > "$RAW/files.txt"
wc -l < "$RAW/files.txt"
tr '\n' '\0' < "$RAW/files.txt" | xargs -0 wc -l | grep -v ' total$' | sort -rn > "$RAW/loc.txt"
head -25 "$RAW/loc.txt"
awk '{split($2, p, "/"); top = (p[1] == "services" || p[1] == "apps" || p[1] == "packages" || p[1] == "tests") ? p[1] "/" p[2] : p[1]; lines[top] += $1; count[top] += 1} END {for (t in lines) printf "%s: %d files, %d lines\n", t, count[t], lines[t]}' "$RAW/loc.txt" | sort
wc -l packages/api-client/src/generated.ts packages/db-types/src/generated.ts contracts/generated/openapi.json`

const MEASURE_PYTHON = String.raw`TS=__RUN_TS__; RAW=.checks/reviews/review-$TS
python3.12 -I - "$RAW" <<'PY'
import ast, json, sys
from collections import defaultdict
from pathlib import Path
raw = Path(sys.argv[1])
files = [f for f in (raw / 'files.txt').read_text().split() if f.endswith('.py')]
def area(f):
    parts = f.split('/')
    if f.startswith('services/agent/src/autobots/') and len(parts) > 5:
        return '/'.join(parts[:5])
    if f.startswith('services/agent/'):
        return '/'.join(parts[:3])
    if f.startswith('tests/') and len(parts) > 2:
        return '/'.join(parts[:2])
    return parts[0] if len(parts) > 1 else '(root)'
funcs, per_file = [], {}
for f in files:
    src = Path(f).read_text()
    tree = ast.parse(src)
    lines = src.splitlines()
    s = dict(lines=len(lines), public=0, documented=0, module_docstring=ast.get_docstring(tree) is not None,
             broad_except=0, type_ignores=src.count('type: ignore'))
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and (node.type is None or (isinstance(node.type, ast.Name) and node.type.id in {'Exception', 'BaseException'})):
            s['broad_except'] += 1
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith('_'):
                s['public'] += 1
                s['documented'] += ast.get_docstring(node) is not None
            a = node.args
            funcs.append(dict(file=f, name=node.name, line=node.lineno, length=node.end_lineno - node.lineno + 1,
                              args=len(a.posonlyargs) + len(a.args) + len(a.kwonlyargs)))
    per_file[f] = s
funcs.sort(key=lambda x: -x['length'])
(raw / 'py_functions.json').write_text(json.dumps(funcs))
(raw / 'py_files.json').write_text(json.dumps(per_file))
agg = defaultdict(lambda: defaultdict(int))
for f, s in per_file.items():
    g = agg[area(f)]
    g['files'] += 1; g['lines'] += s['lines']; g['public'] += s['public']; g['documented'] += s['documented']
    g['no_module_doc'] += not s['module_docstring']; g['broad_except'] += s['broad_except']; g['type_ignores'] += s['type_ignores']
for fn in funcs:
    g = agg[area(fn['file'])]
    g['functions'] += 1
    for t in (40, 80, 150):
        g['over' + str(t)] += fn['length'] > t
print('| Area | Files | Lines | Functions | Over 40 lines | Over 80 | Over 150 | Public functions documented | Files without module docstring | Broad except | type: ignore |')
print('|---|---|---|---|---|---|---|---|---|---|---|')
for k in sorted(agg):
    g = agg[k]
    pct = str(round(100 * g['documented'] / g['public'])) + '%' if g['public'] else '-'
    print(f"| {k} | {g['files']} | {g['lines']} | {g['functions']} | {g['over40']} | {g['over80']} | {g['over150']} | {pct} | {g['no_module_doc']} | {g['broad_except']} | {g['type_ignores']} |")
print()
print('| Lines | Function | Location | Parameters |')
print('|---|---|---|---|')
for fn in funcs[:40]:
    print(f"| {fn['length']} | {fn['name']} | {fn['file']}:{fn['line']} | {fn['args']} |")
PY`

const MEASURE_RUFF = String.raw`TS=__RUN_TS__; RAW=.checks/reviews/review-$TS
(cd services/agent && .venv/bin/ruff check --no-cache --quiet src tests; echo "project ruff exit=$?")
(cd services/agent && .venv/bin/ruff check --no-cache --exit-zero --statistics --select ALL src) > "$RAW/ruff_all_src.txt" 2>/dev/null; head -45 "$RAW/ruff_all_src.txt"
(cd services/agent && .venv/bin/ruff check --no-cache --exit-zero --select C901,PLR0911,PLR0912,PLR0913,PLR0915,PLR0917 --config 'lint.mccabe.max-complexity = 10' --output-format json src) > "$RAW/ruff_complexity.json" 2>/dev/null
services/agent/.venv/bin/ruff check --no-cache --isolated --exit-zero --statistics --target-version py312 --line-length 100 --select E,F,W,I,B,UP,ASYNC,RUF scripts tests .claude/hooks > "$RAW/ruff_root.txt" 2>/dev/null; head -25 "$RAW/ruff_root.txt"
services/agent/.venv/bin/ruff format --no-cache --isolated --check --line-length 100 scripts tests .claude/hooks 2>/dev/null | tail -1
python3.12 -I - "$RAW/ruff_complexity.json" <<'PY'
import json, re, sys
from collections import Counter
from pathlib import Path
root = Path.cwd().resolve()
data = json.loads(Path(sys.argv[1]).read_text() or '[]')
def measured(d):
    found = re.search(r'\((\d+) >', d['message'])
    return int(found.group(1)) if found else 0
print('| Rule | Hits |')
print('|---|---|')
for code, n in Counter(d['code'] for d in data).most_common():
    print(f'| {code} | {n} |')
print()
print('| Rule | Measured | Message | Location |')
print('|---|---|---|---|')
for d in sorted(data, key=lambda d: (d['code'], -measured(d))):
    where = Path(d['filename']).resolve().relative_to(root)
    print(f"| {d['code']} | {measured(d)} | {d['message'].replace(chr(96), '')} | {where}:{d['location']['row']} |")
PY`

const MEASURE_ESLINT = String.raw`TS=__RUN_TS__; RAW=.checks/reviews/review-$TS; REPORT="$PWD/$RAW/eslint.json"
(cd apps/web && PATH="$HOME/.nvm/versions/node/v$(cat ../../.node-version)/bin:$PATH" node_modules/.bin/eslint --no-cache \
  --rule 'max-lines-per-function: [warn, {max: 60, skipBlankLines: true, skipComments: true}]' \
  --rule 'max-lines: [warn, {max: 300, skipBlankLines: true, skipComments: true}]' \
  --rule 'complexity: [warn, 10]' --rule 'max-depth: [warn, 4]' --rule 'max-params: [warn, 4]' --rule 'max-statements: [warn, 25]' \
  --rule 'react/no-multi-comp: [warn, {ignoreStateless: false}]' \
  --rule '@typescript-eslint/no-non-null-assertion: warn' --rule '@typescript-eslint/no-explicit-any: warn' \
  --rule '@typescript-eslint/consistent-type-assertions: [warn, {assertionStyle: never}]' \
  --format json -o "$REPORT" app components lib tests; echo "eslint exit=$? (0 means the project's own rules pass; the extra rules only warn)")`

const MEASURE_SUMMARY = String.raw`TS=__RUN_TS__; RAW=.checks/reviews/review-$TS
python3.12 -I - "$RAW" <<'PY'
import json, re, sys
from collections import Counter, defaultdict
from pathlib import Path
raw = Path(sys.argv[1])
root = Path.cwd().resolve()
def rel(p):
    return str(Path(p).resolve().relative_to(root))
eslint = json.loads((raw / 'eslint.json').read_text())
totals, sizes, complexity, per_file = Counter(), [], [], defaultdict(Counter)
for f in eslint:
    name = rel(f['filePath'])
    for m in f['messages']:
        rule = m.get('ruleId') or 'parse-error'
        totals[rule] += 1
        per_file[name][rule] += 1
        what = re.match(r"^(.*?) has (too many lines|a complexity)", m['message'])
        label = what.group(1) if what else '?'
        count = re.search(r'\((\d+)\)', m['message'])
        if rule == 'max-lines-per-function' and count:
            sizes.append((int(count.group(1)), name, m['line'], label))
        score = re.search(r'complexity of (\d+)', m['message'])
        if rule == 'complexity' and score:
            complexity.append((int(score.group(1)), name, m['line'], label))
print('| ESLint rule (extra rules warn only) | Hits |')
print('|---|---|')
for rule, n in totals.most_common():
    print(f'| {rule} | {n} |')
sizes.sort(reverse=True)
complexity.sort(reverse=True)
print()
print('| Lines (no blanks or comments) | Function | Location |')
print('|---|---|---|')
for n, name, line, label in [s for s in sizes if '/tests/' not in s[1]][:30]:
    print(f'| {n} | {label} | {name}:{line} |')
print()
print('| Complexity | Function | Location |')
print('|---|---|---|')
for n, name, line, label in [c for c in complexity if '/tests/' not in c[1]][:20]:
    print(f'| {n} | {label} | {name}:{line} |')
print()
print('| File | Type assertions | Non-null assertions | Components in file |')
print('|---|---|---|---|')
for name, c in sorted(per_file.items(), key=lambda kv: -kv[1]['@typescript-eslint/consistent-type-assertions']):
    a, nn, mc = c['@typescript-eslint/consistent-type-assertions'], c['@typescript-eslint/no-non-null-assertion'], c['react/no-multi-comp']
    if '/tests/' not in name and (a or nn or mc):
        print(f'| {name} | {a} | {nn} | {mc + 1 if mc else 1} |')
loc = {}
for line in (raw / 'loc.txt').read_text().splitlines():
    parts = line.split(None, 1)
    if len(parts) == 2:
        loc[parts[1]] = int(parts[0])
notes = defaultdict(list)
for fn in json.loads((raw / 'py_functions.json').read_text()):
    if fn['length'] >= 60:
        notes[fn['file']].append(f"{fn['name']}@{fn['line']} is {fn['length']} lines")
for d in json.loads((raw / 'ruff_complexity.json').read_text() or '[]'):
    notes[rel(d['filename'])].append(f"{d['code']}@{d['location']['row']}: {d['message'].replace(chr(96), '')}")
for f in eslint:
    name = rel(f['filePath'])
    for m in f['messages']:
        if m.get('ruleId') in ('max-lines-per-function', 'complexity', 'max-depth', 'max-params'):
            notes[name].append(f"{m['ruleId']}@{m['line']}: {m['message']}")
    c = per_file[name]
    if c['@typescript-eslint/consistent-type-assertions']:
        notes[name].append(f"{c['@typescript-eslint/consistent-type-assertions']} type assertions")
    if c['react/no-multi-comp']:
        notes[name].append(f"{c['react/no-multi-comp'] + 1} components in the file")
files = (raw / 'files.txt').read_text().split()
leads = [{'file': f, 'loc': loc.get(f, 0), 'notes': '; '.join(notes.get(f, []))[:1500]}
         for f in files if loc.get(f, 0) >= 300 or notes.get(f)]
(raw / 'file_metrics.json').write_text(json.dumps(leads, indent=1))
print()
print(f'{len(leads)} files have leads, written to file_metrics.json')
PY`

const MEASURE_REPORTS = String.raw`for p in harness fast full db operations; do f=.checks/$p/latest.json; [ -f "$f" ] && python3.12 -I -c 'import json, sys; d = json.load(open(sys.argv[1])); c = d.get("checks", []); print(sys.argv[2], d.get("status"), d.get("completed_at_utc"), sum(1 for x in c if x.get("status") == "passed"), "of", len(c), "checks passed")' "$f" "$p"; done`

// A resumed run trusts disk, not the run cache: the cache replays agent calls in order, and
// parallel agents finish in a different order each time, so a cache resume redoes finished work.
// __TS__ is the run's timestamp; __KEYS__ is every area and lens key, comma-separated.
const INVENTORY_PY = String.raw`TS=__TS__; OUT=docs/reviews/review-$TS; RAW=.checks/reviews/review-$TS
python3.12 -I - "$OUT" "$RAW" "__KEYS__" <<'PY'
import json, re, subprocess, sys
from pathlib import Path
out, raw, keys = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3].split(',')
problems = []
files = (raw / 'files.txt').read_text().split() if (raw / 'files.txt').is_file() else []
metrics = (out / 'metrics.md').read_text() if (out / 'metrics.md').is_file() else ''
found = re.search(r'\b[0-9a-f]{40}\b', metrics)
revision = found.group(0) if found else ''
head = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
if revision and head and head != revision:
    problems.append(f'HEAD is now {head}, but the review measured {revision}')
dirty = len(subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True).stdout.splitlines())
parts = []
for key in keys:
    part = {'key': key, 'verified': False, 'savedReview': '', 'high': 0, 'medium': 0, 'low': 0, 'rejected': 0, 'notCovered': ''}
    json_file, md_file = out / 'findings' / f'{key}.json', out / 'findings' / f'{key}.md'
    if json_file.is_file() and md_file.is_file():
        try:
            data = json.loads(json_file.read_text())
            for finding in data['findings']:
                part[finding['severity']] += 1
            part['rejected'] = len(data.get('rejected', []))
            part['notCovered'] = data.get('notCovered', '')
            part['verified'] = True
        except (ValueError, KeyError, TypeError) as error:
            problems.append(f'{json_file} is unusable ({error}), so the part is verified again')
            part.update(high=0, medium=0, low=0, rejected=0)
    saved = raw / 'reviews' / f'{key}.json'
    if saved.is_file():
        try:
            data = json.loads(saved.read_text())
            if not isinstance(data.get('findings'), list):
                raise ValueError('it has no findings list')
            part['savedReview'] = str(saved)
            if not part['verified']:
                part['notCovered'] = data.get('notCovered', '')
        except ValueError as error:
            problems.append(f'{saved} is unusable ({error}), so the part is reviewed again')
    parts.append(part)
stop = '' if files and revision else f'Nothing to resume in {out}: files.txt or the revision in metrics.md is missing'
print(json.dumps({'stop': stop, 'timestamp': raw.name.removeprefix('review-'), 'outDir': str(out), 'rawDir': str(raw),
                  'revision': revision, 'dirtyFiles': dirty, 'files': files, 'toolProblems': '; '.join(problems), 'parts': parts}))
PY`

// ---------------------------------------------------------------- lens instructions
// RAW_DIR is replaced with the run's raw folder when the prompt is built.

const BOUNDARIES_FOCUS = String.raw`Map dependency direction, compare it with the intended layering, and compare the layout with DH-03.

1. Python imports between packages, and framework imports per layer:
python3.12 -I - <<'PY'
import ast
from collections import Counter
from pathlib import Path
base = Path('services/agent/src/autobots')
FRAMEWORKS = {'fastapi', 'starlette', 'psycopg', 'psycopg_pool', 'langgraph', 'langchain', 'langchain_core', 'langchain_openrouter', 'deepagents', 'httpx', 'openrouter', 'uvicorn', 'jwt', 'cryptography'}
edges, framework = Counter(), Counter()
for path in sorted(base.rglob('*.py')):
    parts = path.relative_to(base).parts
    layer = parts[0] if len(parts) > 1 else '(package)'
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names = [node.module]
        elif isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        else:
            continue
        for name in names:
            if name.startswith('autobots.'):
                target = name.split('.')[1]
                if target != layer:
                    edges[(layer, target)] += 1
            elif name.split('.')[0] in FRAMEWORKS:
                framework[(layer, name.split('.')[0])] += 1
print('Internal imports, from -> to: count')
for (a, b), n in sorted(edges.items()):
    print(f'  {a} -> {b}: {n}')
print('Framework imports by layer')
for (a, b), n in sorted(framework.items()):
    print(f'  {a}: {b} {n}')
PY
The intended direction: domain imports nothing internal; contracts may use domain; application uses domain, contracts and persistence; adapters, api and operations sit at the edge. Report upward imports, cycles, and framework imports in domain or contracts, naming the files (grep for them).
2. Web: lib/ should not import components; no "use client" module should import a server-only module (bff.ts, server-config.ts, session.ts, or anything that reads secret environment variables); pages should stay thin. Find how components reach the API: the generated client, a BFF helper or raw fetch. Useful: grep -rln '"use client"' apps/web/app apps/web/components | wc -l and grep -rn 'from "@/lib' apps/web/components.
3. Structure: compare services/agent/src/autobots and the repository layout with DH-03, which lists api, domain, application, adapters, workers, graphs and contracts, and scripts/db. For each difference, say whether the code or the document should change.
4. Cohesion: flag modules that hold several unrelated responsibilities, and directories that have grown too broad (application/ holds over forty modules). Propose groupings only where they would reduce coupling or make ownership clearer.`

const DUPLICATION_FOCUS = String.raw`Find logic, data or setup repeated where a shared helper belongs.

1. Start with this detector of repeated 8-line windows. It normalizes whitespace and skips imports and comments. Treat its output as leads, and open the code for every cluster you report:
python3.12 -I - RAW_DIR/files.txt <<'PY'
import hashlib, re, sys
from collections import defaultdict
from pathlib import Path
files = [f for f in Path(sys.argv[1]).read_text().split() if f.endswith(('.py', '.ts', '.tsx', '.sql'))]
WINDOW, MIN_CHARS = 8, 240
windows = defaultdict(list)
for f in files:
    norm = []
    for number, line in enumerate(Path(f).read_text(errors='ignore').splitlines(), 1):
        text = re.sub(r'\s+', ' ', line.strip())
        if len(text) < 4 or text.startswith(('#', '//', '*', '/*', 'import ', 'from ', '"""')):
            continue
        norm.append((number, text))
    for k in range(len(norm) - WINDOW + 1):
        chunk = '\n'.join(t for _, t in norm[k:k + WINDOW])
        if len(chunk) >= MIN_CHARS:
            windows[hashlib.sha1(chunk.encode()).hexdigest()].append((f, norm[k][0]))
pairs = defaultdict(list)
for hits in windows.values():
    if len(hits) < 2:
        continue
    first = {}
    for f, line in hits:
        first.setdefault(f, line)
    names = sorted(first)
    if len(names) == 1:
        lines = sorted({line for _, line in hits})
        if lines[-1] - lines[0] >= WINDOW:
            pairs[(names[0], names[0])].append((lines[0], lines[-1]))
        continue
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            pairs[(names[i], names[j])].append((first[names[i]], first[names[j]]))
ranked = sorted(pairs.items(), key=lambda kv: -len(kv[1]))
print(f'{len(ranked)} file pairs share at least one {WINDOW}-line window')
for (a, b), hits in ranked[:60]:
    where = ', '.join(f'{x}/{y}' for x, y in hits[:4])
    print(f'{len(hits):4} shared windows  {a} <-> {b}  first lines {where}')
PY
2. Then check these suspects directly: fetch, CSRF and error handling repeated across web components; date, money and number formatting; loading, empty and error rendering; SQL and row-mapping patterns across application modules; HTTP request and error mapping across the GitHub, Tavily, Jina and market-data adapters; argument parsing, subprocess calls and report writing across scripts/qualify_*.py; setup and assertions across the tests/db checks and the Playwright specs.
3. Separate harmful duplication (a rule or behavior that must change in lockstep, so copies can drift) from harmless similarity. Report only the harmful kind, and list every copy. SQL repeated across migrations is expected, because a later migration redefines a function or policy, and applied migrations never change: report it only if the current definition is hard to find, and propose a forward fix.`

const TYPES_FOCUS = String.raw`Find where types stop protecting a boundary. DH-06 forbids blanket type assertions that conceal contract mismatches, and asks for explicit parsing at untrusted boundaries.

1. TypeScript: list the assertions ESLint found. With assertion style "never", it reports every "as" except "as const":
python3.12 -I - RAW_DIR/eslint.json <<'PY'
import json, sys
from pathlib import Path
root = Path.cwd().resolve()
for f in json.loads(Path(sys.argv[1]).read_text()):
    for m in f['messages']:
        if m.get('ruleId') in ('@typescript-eslint/consistent-type-assertions', '@typescript-eslint/no-non-null-assertion'):
            print(f"{Path(f['filePath']).resolve().relative_to(root)}:{m['line']}  {m['ruleId'].split('/')[-1]}")
PY
Open each and classify it: an assertion on fetched JSON (contract drift hidden at a trust boundary), DOM or event narrowing, or harmless. Check how components read API responses: the generated @autobots/api-client types, runtime parsing, or casts. Useful: grep -rn "fetch(" apps/web/components apps/web/app apps/web/lib and grep -rln "@autobots/api-client" apps/web.
2. Python: find where Any, dict[str, Any], cast() and type: ignore concentrate:
(cd services/agent && .venv/bin/ruff check --no-cache --exit-zero --select ANN401 --output-format concise src | cut -d: -f1 | sort | uniq -c | sort -rn | head -20)
grep -rnE "dict\[str, Any\]|cast\(|type: ignore" services/agent/src | cut -d: -f1 | sort | uniq -c | sort -rn | head -20
Judge whether payload dictionaries should be TypedDicts, dataclasses or Pydantic models, whether states use Literal or Enum consistently, and whether each type: ignore names a code and a reason.
3. Note that the Python in scripts/, tests/ and .claude/hooks/ is outside mypy, and say what that costs.`

const DOCS_FOCUS = String.raw`Judge whether comments, docstrings and names tell readers what they need. DH-06 asks code to explain nonobvious invariants and to avoid comments that restate syntax.

1. Docstring coverage and module docstrings by area are in RAW_DIR/py_files.json and metrics.md. Sample public functions without docstrings in application/ and api/, and say which need one.
2. Read a sample of comments in the largest modules of each language. Classify them: explains why or an invariant (good), restates the code (noise), or stale and contradicted by the code (defect).
3. Count references to decisions and stories in source:
grep -rnoE "Decision [0-9]{4}|US-[0-9]+\.[0-9]+" apps/web/app apps/web/components apps/web/lib services/agent/src scripts | cut -d: -f1 | sort | uniq -c | sort -rn | head -20
They are deliberate traceability. Judge whether each explains the rule it cites or only points at it.
4. Commented-out code and magic values:
(cd services/agent && .venv/bin/ruff check --no-cache --exit-zero --select ERA001,PLR2004 --statistics src)
5. READMEs: which apps and packages have one, and whether it says how to run, test and extend them.
6. Naming: file naming per language, function and variable names, abbreviations, boolean names, constants, and names that disagree with behavior.`

const ERRORS_FOCUS = String.raw`Judge whether errors are typed, handled, logged and shown consistently. DH-06 asks for centralized error handling, preserved causes in private logs, safe typed errors, and no swallowed exceptions.

1. Broad handlers in Python, with their files:
(cd services/agent && .venv/bin/ruff check --no-cache --exit-zero --select BLE001,S110,S112,E722 --output-format concise src)
services/agent/.venv/bin/ruff check --no-cache --isolated --exit-zero --select BLE001,S110,S112,E722 --output-format concise scripts tests .claude/hooks | head -60
Open each one. Decide whether it is a justified process boundary that logs, reports or re-raises, or whether it swallows a failure.
2. Exception classes: grep -rnE "^class [A-Za-z_]+\(.*(Exception|Error)" services/agent/src. Is there a hierarchy, and do API errors map through api/errors.py consistently?
3. Cancellation: confirm asyncio.CancelledError is never swallowed (grep -rn "CancelledError" services/agent/src).
4. Logging: print versus the JSON logger in operations/logs.py, what is logged at which level, and that secrets and message text are never logged.
5. Web: how BFF route handlers map upstream errors, and how components show errors (grep -rn "catch" apps/web/components | wc -l, then compare three screens). Are loading, empty, denied, unavailable and retryable states represented deliberately, as DH-06 asks?`

const TOOLING_FOCUS = String.raw`Map which standards a tool enforces and where enforcement stops. Read services/agent/pyproject.toml, apps/web/eslint.config.mjs, apps/web/tsconfig.json, apps/web/package.json, packages/api-client/tsconfig.json and package.json, the root package.json, scripts/toolchain.py (which checks run, and on which paths) and scripts/verify.py.

1. Use the numbers in metrics.md: the repository-level Python under the service's ruff rules, the files ruff format would change, the ruff ALL superset and the extra ESLint rules.
2. Propose rule additions that would have caught real findings. Give each the count it would flag today, a warn or baseline step, and the exact configuration: for ruff, lint.select, per-file-ignores and the mccabe and pylint settings; for the ESLint flat config, complexity, max-lines-per-function, max-lines, @typescript-eslint/consistent-type-assertions and no-restricted-imports for layering.
3. Is a formatter configured for the web (Prettier settings), and do the service, scripts and tests share one Python style? Compare quote style and line length in scripts/ with services/agent.
4. Test runners: pytest in services/agent, unittest in tests/harness, the runner of the web unit tests, and Playwright. Is the split deliberate and documented?
5. No CI configuration is tracked (.github holds no files). Say what a minimal local pre-commit hook or CI job would run, using the scripts/verify.py profiles.
6. Check rule names with services/agent/.venv/bin/ruff rule <CODE>, and ESLint rule availability under apps/web/node_modules.`

const WEB_ARCHITECTURE_FOCUS = String.raw`Judge whether the screens share one approach to data, state, forms and view states.

1. Client and server split: grep -rln '"use client"' apps/web/app apps/web/components | wc -l. Which pages are Server Components that load data on the server, and which screens fetch in effects?
2. Data fetching: compare patterns such as useEffect with fetch, polling, EventSource, server loading in pages, and lib helpers. Useful: grep -rn "useEffect" apps/web/components | wc -l and grep -rnE "setInterval|EventSource" apps/web/components apps/web/lib.
3. Custom hooks: grep -rn "export function use" apps/web. Is shared behavior extracted into hooks, or repeated inside components?
4. State: screens with many useState calls (grep -c "useState" apps/web/components/*.tsx | sort -t: -k2 -rn | head), derived state kept in state, and reducer candidates.
5. View states: how loading, empty, error, denied and saved states render across screens, and whether a shared component exists.
6. Files holding several components (react/no-multi-comp in metrics.md), component naming, and colocated helpers that belong in lib/.
7. Styling: use of the components/ui primitives versus ad-hoc class strings, and of the Luma tokens in PRD-Design-System.md.
Compare at least three screens from different areas side by side before you report a pattern.`

// ---------------------------------------------------------------- areas and lenses

const RULES = {
  web: '.claude/rules/nextjs.md; PRD-Development-Harness.md DH-06, "Next.js and TypeScript"; PRD-Design-System.md DS-01 to DS-05',
  python: '.claude/rules/python-worker.md; .claude/rules/contracts.md; PRD-Development-Harness.md DH-06, "Python API, domain and workers" and "Models, contracts and state"',
  durable: '.claude/rules/python-worker.md; .claude/rules/model-gateway.md; .claude/rules/contracts.md; PRD-Development-Harness.md DH-06, "Python API, domain and workers", "Models, contracts and state" and "Durable workers and model gateway"; docs/engineering/option-b-contract.md, the parts on states, transitions and recovery',
  db: '.claude/rules/database.md; .claude/rules/infrastructure.md; PRD-Development-Harness.md DH-07 and DH-08',
  tooling: '.claude/rules/delivery.md; .claude/rules/infrastructure.md; PRD-Development-Harness.md DH-03, DH-05, DH-06 and DH-09',
  all: 'every .claude/rules/*.md; PRD-Development-Harness.md DH-03 and DH-06',
}

const WEB = 'apps/web/'
const COMPONENTS = 'apps/web/components/'
const PACKAGE = 'services/agent/src/autobots/'
const APPLICATION = 'services/agent/src/autobots/application/'
const components = (...names) => names.map((name) => COMPONENTS + name)
const application = (...names) => names.map((name) => APPLICATION + name)

// A file goes to the area whose list names it, otherwise to the area with the longest matching
// prefix. Each top-level directory has a catch-all prefix, so a new file still gets reviewed.
const AREAS = [
  {
    key: 'web-run', id: 'WRUN', kind: 'area', title: 'Web: run screens', rules: RULES.web,
    files: components('run-workspace.tsx', 'run-list.tsx', 'run-inspector.tsx', 'run-panel.tsx', 'tool-uses.tsx', 'run-disclosure.tsx', 'run-controls.tsx', 'unknown-effects.tsx', 'continue-run.tsx', 'new-run.tsx'),
    prefixes: [WEB + 'app/runs/'],
    focus: `RunWorkspaceView is the largest and most complex component in the web app. Map its responsibilities: data loading, the event stream and reconnects, deduplication, derived view state and rendering. Propose a target split into hooks, pure view-model functions and child components. Check effect cleanup and aborts; loading, empty, error and denied states; duplicated formatting helpers; and how fetched JSON is typed.`,
  },
  {
    key: 'web-composer', id: 'WCMP', kind: 'area', title: 'Web: composer, home and sessions', rules: RULES.web,
    files: [...components('goal-composer.tsx', 'jobs-chart.tsx', 'home-activity.tsx', 'search-palette.tsx', 'session-panel.tsx', 'data-summary.tsx', 'waiting-notifier.tsx', 'home-greeting.tsx'), WEB + 'app/page.tsx'],
    prefixes: [WEB + 'app/sessions/'],
    focus: `GoalComposer is long and branchy. Review its form state, validation, submission and budget and model choices, and whether a reducer or form hook would simplify it. Review jobs-chart for separation of scale math from rendering, the home page's server-side data loading, search-palette keyboard handling, session-panel, and polling in waiting-notifier (timers, cleanup and backoff).`,
  },
  {
    key: 'web-build', id: 'WBLD', kind: 'area', title: 'Web: workflows and Experts', rules: RULES.web,
    files: components('workflow-editor.tsx', 'workflows-panel.tsx', 'workflow-monitor.tsx', 'experts-panel.tsx', 'expert-editor.tsx'),
    prefixes: [WEB + 'app/workflows/', WEB + 'app/workflow-executions/', WEB + 'app/experts/'],
    focus: `Review editor state in workflow-editor and expert-editor: drafts, dirty tracking, validation and saving, and how the workflow IR is edited and previewed. Compare experts-panel with workflows-panel for list and detail patterns that a shared component or hook could own. Check how workflow-monitor polls or streams.`,
  },
  {
    key: 'web-tools-approvals', id: 'WTAP', kind: 'area', title: 'Web: tool catalog and approvals', rules: RULES.web,
    files: components('tool-catalog.tsx', 'approvals-panel.tsx'),
    prefixes: [WEB + 'app/tools/', WEB + 'app/approvals/'],
    focus: `tool-catalog.tsx and approvals-panel.tsx are each about 800 lines holding several components. Propose how to split them by responsibility. Review the approvals keyboard handler (onKey), decision flows and optimistic updates, the tool guide modal, and schema rendering (FieldTable).`,
  },
  {
    key: 'web-system', id: 'WSYS', kind: 'area', title: 'Web: operations and settings', rules: RULES.web,
    files: components('operations-panel.tsx', 'model-policy-panel.tsx', 'provider-settings-panel.tsx', 'keys-and-vars-panel.tsx', 'appearance-control.tsx'),
    prefixes: [WEB + 'app/settings/', WEB + 'app/operations/'],
    focus: `Review the settings and operations panels as a family: use of the shared form controls (a harness test requires components/ui/field.tsx), save and validate flows, how secrets stay out of props and caches, value formatting in operations-panel (valueFor), and whether loading, error and saved states look and behave the same across panels.`,
  },
  {
    key: 'web-shell', id: 'WSHL', kind: 'area', title: 'Web: shell, BFF, lib and configuration', rules: RULES.web + '; .claude/rules/contracts.md for packages/api-client',
    files: [],
    prefixes: [WEB, 'packages/api-client/'],
    focus: `Review the BFF route handlers and lib/ (bff.ts, request-guard.ts, csrf-fetch.ts, session.ts, server-config.ts) for consistent session and workspace checks on every operation, CSRF and Origin protection, error mapping and server-only boundaries. Review the shared UI primitives in components/ui and whether screens use them, the shell and navigation components, the api-client runtime, the web configuration (tsconfig, ESLint, Next.js, PostCSS and package scripts) and the unit tests.`,
  },
  {
    key: 'py-domain', id: 'PDOM', kind: 'area', title: 'Python: domain, contracts and persistence', rules: RULES.python,
    files: ['services/agent/pyproject.toml'],
    prefixes: [PACKAGE + 'domain/', PACKAGE + 'contracts/', PACKAGE + 'persistence/', 'services/agent/'],
    focus: `Check that domain/ stays pure: no IO, HTTP, database or LangGraph imports. Review value types, enums and Literals, invariants, and where validation lives. Review the Pydantic conventions in contracts/ (strictness, Field constraints, shared primitives, naming and versioning) and the separation of domain, row, DTO and graph types that the rules require. Check module cohesion and docstrings, and the package configuration in pyproject.toml.`,
  },
  {
    key: 'py-run', id: 'PRUN', kind: 'area', title: 'Python: run lifecycle and model spend', rules: RULES.durable,
    files: application('runs.py', 'goal_loop.py', 'plans.py', 'run_usage.py', 'verification.py', 'recovery.py', 'compaction.py', 'model_admission.py', 'model_attempts.py', 'worker_inference.py', 'profiles.py', 'worker_leases.py', 'run_projection.py'),
    prefixes: [],
    focus: `This is the durable run lifecycle. goal_loop.py is the largest application module: run_goal, _keep_lease and _finish are complex, and admit_run in runs.py takes 15 parameters. Review how SQL and transactions are organized, how state transitions are expressed (one transition table, or updates scattered across modules), cancellation propagation, the error taxonomy, and the size and cohesion of run_projection.py. Propose parameter objects and extractions that keep leases, fencing and receipts intact.`,
  },
  {
    key: 'py-tools', id: 'PTOL', kind: 'area', title: 'Python: tools and approvals', rules: RULES.durable,
    files: application('tool_gateway.py', 'tools.py', 'tool_catalog.py', 'tool_grants.py', 'tool_uses.py', 'code_tools.py', 'browsing_loop.py', 'browsing_tool.py', 'reconciliation.py', 'approvals.py', 'cronjob_tool.py', 'tool_keys.py', 'tool_key_settings.py'),
    prefixes: [],
    focus: `tool_gateway._dispatch has 15 return statements and a complexity of 19, and a function in approvals.py takes 18 parameters. Review how tools are defined and registered, receipts and reconciliation, the order of tool key resolution, how approval requests are built, and duplication between tool modules. Approvals must stay bound to the normalized effect.`,
  },
  {
    key: 'py-product', id: 'PPRD', kind: 'area', title: 'Python: product services', rules: RULES.python,
    files: application('experts.py', 'assignments.py', 'workflows.py', 'workflow_overview.py', 'workflow_runner.py', 'routines.py', 'memory.py', 'improvements.py', 'artifacts.py', 'search.py'),
    prefixes: [APPLICATION],
    focus: `These are product services over SQL. Look for repeated query and row-mapping patterns, long parameter lists (one workflows function takes 12), assign_tool (complexity 17), workflow_runner._run_block, and module size and cohesion. Say whether shared persistence helpers would reduce duplication without merging row and domain types.`,
  },
  {
    key: 'py-adapters', id: 'PADP', kind: 'area', title: 'Python: adapters', rules: RULES.durable,
    files: [],
    prefixes: [PACKAGE + 'adapters/'],
    focus: `Several tool factories are single closures of 130 to 230 lines: github_pull_request_tool (complexity 37), github_read_tools, tavily_tools and market_tools. Propose a structure for tool adapters, such as module-level functions, small classes, and shared request and error mapping. Review HTTP handling shared by the GitHub, Tavily, Jina and market-data adapters, httpx client ownership and timeouts, loop_middleware._admitted_call, url_guard and the browser executor.`,
  },
  {
    key: 'py-api', id: 'PAPI', kind: 'area', title: 'Python: HTTP API', rules: RULES.python,
    files: [],
    prefixes: [PACKAGE + 'api/'],
    focus: `Review the route modules for consistent dependency injection, membership and auth checks, error mapping through api/errors.py, response models, handler size and parameter counts, business logic inside handlers, the size of run_routes.py, and whether the app factory stays pure for offline OpenAPI generation.`,
  },
  {
    key: 'py-ops', id: 'POPS', kind: 'area', title: 'Python: operations, credentials and readiness', rules: RULES.durable + '; .claude/rules/infrastructure.md',
    files: application('operations.py', 'retention.py', 'provider_settings.py', 'schema_release.py'),
    prefixes: [PACKAGE + 'operations/', APPLICATION + 'credentials/'],
    focus: `Review the process entry points (worker.py, bootstrap_owner.py and concept_seed.py) and the paid trial runners (route_qualification, reasoning_trial and browse_trial, whose run_trial is about 190 lines). Check broad except clauses at process boundaries, print versus structured logging, the readiness checks in application/operations.py (REQUIRED_RELATIONS and REQUIRED_COLUMNS), retention, provider settings, and the clarity of the credentials crypto modules.`,
  },
  {
    key: 'py-tests', id: 'PTST', kind: 'area', title: 'Python: service tests', rules: RULES.python + '; .claude/rules/model-gateway.md, on fake transports',
    files: [],
    prefixes: ['services/agent/tests/'],
    focus: `test_worker_inference.py is over 1,100 lines. Review fixture and factory reuse (conftest.py is small), the fake OpenRouter transport, parametrization, naming, assertion helpers, the many type: ignore comments, and duplication with tests/db.`,
  },
  {
    key: 'db-tests', id: 'TDBC', kind: 'area', title: 'Tests: database, worker and fault checks', rules: RULES.db + '; .claude/rules/python-worker.md',
    files: [],
    prefixes: ['tests/db/', 'tests/web/', 'tests/faults/', 'tests/qualification/'],
    focus: `The tests/db checks are scripts whose main() functions run 150 to 320 lines. Review how they are structured and invoked (scripts/app_db.py and scripts/disposable_db.py), shared helpers versus copy and paste, assertion and failure reporting, broad except clauses, and naming (_check, _worker, _live and _script). Include the tests/web fixtures, tests/faults and tests/qualification.`,
  },
  {
    key: 'web-tests', id: 'TWEB', kind: 'area', title: 'Tests: browser suites', rules: RULES.web,
    files: [WEB + 'playwright.config.ts'],
    prefixes: [WEB + 'tests/browser/'],
    focus: `Review Playwright spec size (slice-visual.spec.ts is over 1,000 lines), shared fixtures and page helpers, the selector strategy (roles and labels versus CSS), waits, duplication across the slice-*.spec.ts files, accessibility checks with axe, and naming and organization.`,
  },
  {
    key: 'harness-tests', id: 'THRN', kind: 'area', title: 'Tests: harness and toolchain', rules: RULES.tooling,
    files: [],
    prefixes: ['tests/harness/', 'tests/toolchain/', 'tests/'],
    focus: `Review the harness and toolchain tests: unittest versus pytest, very long files (test_assistant_assets.py and test_hooks.py), how fixtures are built, duplication, and readability.`,
  },
  {
    key: 'scripts', id: 'SCRP', kind: 'area', title: 'Scripts and hooks', rules: RULES.tooling,
    files: ['package.json'],
    prefixes: ['scripts/', '.claude/hooks/'],
    focus: `About 10,000 lines of operational Python that ruff and mypy never check: only services/agent is linted and type-checked. Several qualify() and attempt() functions run 215 to 410 lines. Review module organization, the shared harness_lib, duplication across qualify_*.py (arguments, subprocess calls and reports), error handling at process boundaries, the hook dispatcher, and style divergence from services/agent.`,
  },
  {
    key: 'sql-infra', id: 'SQLI', kind: 'area', title: 'SQL, infrastructure and Makefile', rules: RULES.db,
    files: ['Makefile'],
    prefixes: ['supabase/', 'infra/', 'packages/db-types/'],
    focus: `Review migration size and naming; consistency of RLS policies, grants and security definer functions; comments in SQL; the reference seed; the Compose files and Dockerfiles; the packages/db-types configuration; and the Makefile. Never propose editing an applied migration.`,
  },
]

const SWEEPS = [
  { key: 'sweep-boundaries', id: 'XMOD', kind: 'lens', title: 'Lens: module boundaries and dependency direction', rules: RULES.all, focus: BOUNDARIES_FOCUS },
  { key: 'sweep-duplication', id: 'XDUP', kind: 'lens', title: 'Lens: duplication and reuse', rules: RULES.all, focus: DUPLICATION_FOCUS },
  { key: 'sweep-types', id: 'XTYP', kind: 'lens', title: 'Lens: types and contracts at boundaries', rules: RULES.all, focus: TYPES_FOCUS },
  { key: 'sweep-docs-naming', id: 'XDOC', kind: 'lens', title: 'Lens: comments, documentation and naming', rules: RULES.all, focus: DOCS_FOCUS },
  { key: 'sweep-errors', id: 'XERR', kind: 'lens', title: 'Lens: errors, logging and view states', rules: RULES.all, focus: ERRORS_FOCUS },
  { key: 'sweep-tooling', id: 'XTOL', kind: 'lens', title: 'Lens: standards enforcement and tooling', rules: RULES.all, focus: TOOLING_FOCUS },
  { key: 'sweep-web-architecture', id: 'XWEB', kind: 'lens', title: 'Lens: web UI architecture', rules: RULES.web, focus: WEB_ARCHITECTURE_FOCUS },
]

const SPEC = Object.fromEntries([...AREAS, ...SWEEPS].map((spec) => [spec.key, spec]))

// One verifier per group. Related parts share a verifier because it reads the same code.
const GROUPS = [
  ['web-run', 'web-composer'],
  ['web-build', 'web-tools-approvals'],
  ['web-system', 'web-shell'],
  ['py-domain', 'py-run'],
  ['py-tools', 'py-product'],
  ['py-adapters', 'py-api'],
  ['py-ops', 'scripts'],
  ['db-tests', 'sql-infra'],
  ['web-tests', 'harness-tests'],
  ['py-tests'],
  ['sweep-boundaries', 'sweep-duplication'],
  ['sweep-types', 'sweep-docs-naming'],
  ['sweep-errors', 'sweep-tooling'],
  ['sweep-web-architecture'],
]

// ---------------------------------------------------------------- the link and ID checker

const LINK_CHECKER = String.raw`python3.12 -I - __OUT__ <<'PY'
import json, re, sys
from pathlib import Path
out = Path(sys.argv[1])
link = re.compile(r'\[[^\]]*\]\(([^)\s]+)\)')
anchors = re.compile(r'<a id="([^"]+)"></a>')
known = set()
for path in sorted((out / 'findings').glob('*.json')):
    try:
        data = json.loads(path.read_text())
    except ValueError as error:
        print(f'{path}: invalid JSON: {error}')
        continue
    known.update(finding['id'] for finding in data.get('findings', []))
    known.update(item['id'] for item in data.get('rejected', []))
def slug(heading):
    return re.sub(r'\s', '-', re.sub(r'[^\w\s-]', '', heading.strip().lower()))
problems = 0
for md in sorted(out.rglob('*.md')):
    text = md.read_text()
    for target in link.findall(text):
        if target.startswith(('http://', 'https://', 'mailto:')):
            continue
        path, _, fragment = target.partition('#')
        dest = (md.parent / path).resolve() if path else md.resolve()
        if not dest.exists():
            print(f'{md}: missing target {target}')
            problems += 1
            continue
        if fragment[:1] == 'L' and fragment[1:].split('-')[0].isdigit() and dest.is_file():
            line = int(fragment[1:].split('-')[0])
            total = len(dest.read_text(errors='ignore').splitlines())
            if line > total:
                print(f'{md}: {target} is past the end ({total} lines)')
                problems += 1
        elif fragment and dest.suffix == '.md':
            body = dest.read_text()
            if fragment not in anchors.findall(body) and fragment not in {slug(h) for h in re.findall(r'^#+\s+(.*)$', body, re.M)}:
                print(f'{md}: missing anchor {target}')
                problems += 1
    for ref in sorted(set(re.findall(r'\b([A-Z]{4}-\d{2})\b', text)) - known):
        print(f'{md}: unknown finding ID {ref}')
        problems += 1
print(f'{problems} problems')
PY`

// ---------------------------------------------------------------- helpers

function checkConfiguration() {
  const grouped = GROUPS.flat()
  const problems = []
  for (const key of Object.keys(SPEC)) if (!grouped.includes(key)) problems.push(`${key} is in no verification group`)
  for (const key of grouped) if (!SPEC[key]) problems.push(`group names unknown part ${key}`)
  if (new Set(grouped).size !== grouped.length) problems.push('a part appears in two verification groups')
  const ids = [...AREAS, ...SWEEPS].map((spec) => spec.id)
  if (new Set(ids).size !== ids.length) problems.push('two parts share an ID prefix')
  for (const id of ids) if (!/^[A-Z]{4}$/.test(id)) problems.push(`ID prefix ${id} must be four capital letters`)
  if (problems.length) throw new Error(`Workflow configuration: ${problems.join('; ')}`)
}

function assignFiles(files) {
  const assigned = Object.fromEntries(AREAS.map((spec) => [spec.key, []]))
  const unassigned = []
  for (const file of files) {
    let owner = AREAS.find((spec) => spec.files.includes(file))
    if (!owner) {
      let longest = -1
      for (const spec of AREAS) {
        for (const prefix of spec.prefixes) {
          if (file.startsWith(prefix) && prefix.length > longest) {
            owner = spec
            longest = prefix.length
          }
        }
      }
    }
    if (owner) assigned[owner.key].push(file)
    else unassigned.push(file)
  }
  return { assigned, unassigned }
}

// An agent that returns nothing (a usage limit, a terminal API error) gets one more attempt.
// The first attempt keeps its original label and options, so a resumed run still finds it in the
// cache; the retry's label differs, so the two attempts never share a cache entry.
const counters = { agents: 0, retries: 0 }

async function once(prompt, opts) {
  counters.agents += 1
  const first = await agent(prompt, opts)
  if (first) return first
  log(`Retrying ${opts.label}: the first attempt returned nothing.`)
  counters.agents += 1
  counters.retries += 1
  return agent(prompt, { ...opts, label: `${opts.label}:retry` })
}

function withIds(spec, review) {
  return {
    ...review,
    findings: review.findings.map((finding, index) => ({ id: `${spec.id}-${String(index + 1).padStart(2, '0')}`, ...finding })),
  }
}

function leadsFor(spec, ctx) {
  // A resumed run does not carry the leads in memory; they stay on disk from the measure step.
  if (!ctx.fileMetrics.length) return `- Read the entries for these files in ${ctx.rawDir}/file_metrics.json.`
  const scope = new Set(ctx.assigned[spec.key] || [])
  const leads = ctx.fileMetrics.filter((entry) => scope.has(entry.file))
  if (!leads.length) return '- No file in this area crossed the measurement thresholds.'
  return leads.map((entry) => `- ${entry.file} (${entry.loc} lines): ${entry.notes || 'over 300 lines'}`).join('\n')
}

function measurePrompt(requested) {
  const fill = (text) => text.split('__TS__').join(requested).split('__RUN_TS__').join(requested || '__RUN_TS__')
  const block = (text) => '\n```sh\n' + fill(text) + '\n```\n'
  const replaceNote = requested ? '' : ' In later blocks, replace __RUN_TS__ with the timestamp step 1 prints.'
  return `You run the measurement step of a code-quality review of this repository. Change no source file. Use only installed tools: install nothing, start no service and call no model. Run each step below from the repository root as its own command, in order. Shell variables do not survive between commands, so every block sets its own.${replaceNote} If a command fails or is refused, continue and report it in toolProblems.

Step 1. Set up the folders and record the revision. If it prints STOP, return at once with stop set to that line and empty values elsewhere.${block(MEASURE_SETUP)}
Step 2. List the in-scope files and count lines.${block(MEASURE_FILES)}
Step 3. Measure Python functions, docstrings and broad except clauses.${block(MEASURE_PYTHON)}
Step 4. Run ruff: the project's own rules, the ALL superset, the complexity and parameter rules, and the repository-level Python under the service's rules.${block(MEASURE_RUFF)}
Step 5. Run ESLint with extra size, complexity and assertion rules passed on the command line.${block(MEASURE_ESLINT)}
Step 6. Summarize ESLint, and write per-file leads for the reviewers.${block(MEASURE_SUMMARY)}
Step 7. Read the latest verification reports without rerunning them.${block(MEASURE_REPORTS)}
Step 8. Write docs/reviews/review-<timestamp>/metrics.md from what the steps printed, with these sections:
1. Run: timestamp, revision, working-tree state and tool versions.
2. Size: in-scope files and lines by area, the 25 largest files, and the sizes of the generated files, marked out of scope.
3. Python functions and documentation: the area table and the 40 longest functions from step 3.
4. Python complexity and parameters: the tables from step 4.
5. Python rule superset: the top 40 lines of ruff_all_src.txt. Note that ALL is an exploratory superset, not a proposal to enable every rule.
6. Repository-level Python: the statistics from ruff_root.txt and the format count. Note that scripts/, tests/ and .claude/hooks/ are outside the service's ruff and mypy runs.
7. TypeScript and React: the tables from step 6.
8. Baseline checks: the ruff and ESLint exit codes from this run, and the latest verification reports by profile, status and date. Say the reports were read, not rerun.
9. Commands: every command you ran, verbatim, in fenced blocks.
10. Limitations: anything that failed, was refused or is approximate. ESLint line counts skip blank and comment lines, while the Python counts include them.
Keep the tables as printed. Add no findings or opinions; reviewers do that.

Step 9. Return: stop (empty), timestamp, outDir (docs/reviews/review-<timestamp>), rawDir (.checks/reviews/review-<timestamp>), revision (the full commit), dirtyFiles (the count from step 1), files (every line of files.txt, in order), fileMetrics (the entries of file_metrics.json, unchanged), toolProblems and summary.`
}

function inventoryPrompt(requested) {
  const command = INVENTORY_PY.split('__TS__').join(requested).split('__KEYS__').join(Object.keys(SPEC).join(','))
  return `You take stock of a stopped code-quality review so it can continue without redoing finished work. Change no file. Run this one command from the repository root:
\`\`\`sh
${command}
\`\`\`
It prints one JSON object. Return exactly that object, with every field and every list entry unchanged and in order. If the command fails, return stop set to the error, empty values elsewhere and an empty parts list.`
}

function reviewPrompt(spec, ctx) {
  const files = ctx.assigned[spec.key] || []
  const scope = spec.kind === 'area'
    ? `Your area: ${spec.title} (key ${spec.key}).

Files in scope (${files.length}). Read each one in full before you judge it:
${files.map((file) => '- ' + file).join('\n')}

Measured leads for these files. Confirm them by reading; a metric alone is not a finding:
${leadsFor(spec, ctx)}

Questions for this area:
${spec.focus}`
    : `Your lens: ${spec.title} (key ${spec.key}). It covers all in-scope source: ${ctx.files.length} files, listed in ${ctx.rawDir}/files.txt. Area reviewers handle single-file issues. Report patterns that span several files or areas, inconsistencies between areas, and gaps that no single area can see. Open the code behind every pattern you report.

${spec.focus.split('RAW_DIR').join(ctx.rawDir)}`
  return `You are a senior engineer reviewing the Autobots repository for code quality and maintainability. This is one part of a larger review, and other reviewers cover the rest. Change no file.

Read first:
- ${PROMPT_FILE}: "Goal", "Ground rules", "Rubrics" and "Evidence standard" are binding.
- The rules for this part: ${spec.rules}. AGENTS.md is already in your context.
- ${ctx.outDir}/metrics.md for the measured numbers. Raw tool output is in ${ctx.rawDir}.

Revision ${ctx.revision}, review ${ctx.timestamp}.

${scope}

Judge every dimension in "Goal" (${DIMENSIONS.join(', ')}), and tag each finding with the one that fits best. You may run read-only commands: git, grep, rg, wc, sed -n, python3.12 -I scripts that only read files, and ruff or ESLint in check mode. Write nothing, except scratch output under ${ctx.rawDir}/${spec.key}/ if you need it, and the saved copy of your review described at the end. If a command is refused, keep reading files and say so in notCovered.

Return:
- summary: one paragraph on the state of this part.
- scores: one per dimension you can judge (${SCORE_DIMENSIONS.join(', ')}), from 1 to 5, each with a one-line reason.
- strengths: three to eight practices worth keeping and spreading, with file references.
- findings: the most valuable ones, about twenty at most, meeting the evidence standard. Use repository-relative paths. Write "none" in ruleCheck when no rule applies. Give a sketch for every high finding and every size finding.
- filesRead: every file you read in full.
- notCovered: what you could not review and why, or an empty string.

Before you return, save the same object as JSON to ${ctx.rawDir}/reviews/${spec.key}.json, and check it with python3.12 -m json.tool. If this run stops before verification, a resumed run verifies that copy instead of reviewing again.`
}

// entries: { key, kind: 'fresh', review } with IDs assigned, or { key, kind: 'saved', file } for a
// review a stopped run saved to disk.
function verifyPrompt(entries, ctx) {
  const parts = entries.map((entry) => {
    const spec = SPEC[entry.key]
    const files = ctx.assigned[entry.key] || []
    const scope = spec.kind === 'area' ? `${files.length} files: ${files.join(', ')}` : `all in-scope source, listed in ${ctx.rawDir}/files.txt`
    const head = `## ${entry.key}: ${spec.title}
Kind: ${spec.kind}. Finding ID prefix: ${spec.id}. Scope: ${scope}.
Rules: ${spec.rules}.
Write ${ctx.outDir}/findings/${entry.key}.json and ${ctx.outDir}/findings/${entry.key}.md.`
    if (entry.kind === 'saved') {
      return `${head}
The review is saved at ${entry.file}. Read all of it. A finding without an id takes ${spec.id}-01, ${spec.id}-02 and so on, in file order.`
    }
    const { filesRead, ...rest } = entry.review
    return `${head}
The reviewer read ${filesRead.length} files. Review, with finding IDs:
${JSON.stringify(rest, null, 1)}`
  })
  return `You are the adversarial verifier for part of a code-quality review of the Autobots repository. Keep only findings that are true, useful and allowed by the project's rules. When you cannot confirm a finding, reject it.

Read ${PROMPT_FILE} first. "Ground rules", "Rubrics", "Evidence standard" and "Finding format" are binding.

For every finding below:
1. Open every cited location. The code at file:line must match the evidence. Correct small line drift. Reject a finding whose code is missing or does something else.
2. For a pattern finding, recount the occurrences with grep or rg, and correct the count.
3. Test the impact. Keep the finding only if it is real for this codebase and a maintainer would act on it. Reject generic advice and pure taste.
4. Test the recommendation against the ground rules, the rules for its part and, where relevant, docs/engineering/decisions/ (grep the topic). Revise it to comply, or reject it.
5. Calibrate severity, effort and risk with the rubric. Merge duplicates within a part under the lower ID, and list the merged ID as rejected with the reason "merged into <ID>".
6. Keep the reviewer's summary, scores and strengths unless the code contradicts them. Correct them if it does.

Then write exactly the two files named for each part, following "Finding format". Kept findings carry "verdict" ("confirmed" or "revised") and a one-line "verifierNote". Use the schema "autobots.code-review/v1", the timestamp "${ctx.timestamp}" and the revision "${ctx.revision}", and copy the reviewer's notCovered. Link Markdown to source as ../../../../<path>#L<line>. Write no other file and change no source. After writing, check each JSON file with: python3.12 -m json.tool <file> > /dev/null

${parts.join('\n\n')}

Return, for each part, the kept findings (id, severity, dimension, title and verdict), the rejected ones (id and reason) and the files you wrote.`
}

function standardsPrompt(ctx, digest) {
  return `Write ${ctx.outDir}/standards.md and no other file. Change no source.

Verified parts, with kept high/medium/low counts: ${digest}. A part missing from this list has no findings files; say so where it matters.

Read ${PROMPT_FILE} ("Goal", "Ground rules" and "Standards document"), then every ${ctx.outDir}/findings/*.json (the verified findings), ${ctx.outDir}/metrics.md, AGENTS.md, every .claude/rules/*.md, PRD-Development-Harness.md DH-03, DH-06 and DH-09, PRD-Design-System.md, and the current tool configuration: services/agent/pyproject.toml, apps/web/eslint.config.mjs, apps/web/tsconfig.json, apps/web/package.json, packages/api-client/tsconfig.json, packages/api-client/package.json, the root package.json, and scripts/toolchain.py for which checks run on which paths.

Follow "Standards document" exactly. Ground every standard in this repository, with numbers from metrics.md and linked finding IDs (findings/<key>.md#<lowercase id>). Every enforcement snippet must be valid for the installed versions: ruff 0.17, ESLint 9 flat config with eslint-config-next 16, TypeScript 6 and mypy strict. Check ruff rule codes with services/agent/.venv/bin/ruff rule <CODE>, and ESLint rule names against apps/web/node_modules. When a threshold would flag existing code, say how much, and start it at warn or with a baseline. Cite existing rules instead of restating them. Nothing may conflict with the ground rules.

Another writer produces refactor-plan.md at the same time. Refer to plan work by topic, not by item number.`
}

function planPrompt(ctx, digest) {
  return `Write ${ctx.outDir}/refactor-plan.md and no other file. Change no source.

Verified parts, with kept high/medium/low counts: ${digest}. A part missing from this list has no findings files; say so where it matters.

Read ${PROMPT_FILE} ("Goal", "Ground rules" and "Refactor plan"), then every ${ctx.outDir}/findings/*.json (the verified findings), ${ctx.outDir}/metrics.md, AGENTS.md, .claude/rules/delivery.md and .claude/rules/ohmyorch-delivery.md (how work is delivered here).

Follow "Refactor plan" exactly. Group related findings into items; an item may address findings from several areas and lenses. Within each wave, order items by value for effort. For each item, name the scripts/verify.py profile that proves it (harness, fast, full, db or operations) and the tests to add first. Link finding IDs as findings/<key>.md#<lowercase id>. Address every high finding, or defer it with a reason. Edit no backlog: suggest stories only.

Another writer produces standards.md at the same time. Refer to standards by topic, not by number.`
}

function readmePrompt(ctx, facts) {
  return `Write ${ctx.outDir}/README.md. Then copy two files into the review folder with: cp ${PROMPT_FILE} ${ctx.outDir}/PROMPT.md && cp ${WORKFLOW_FILE} ${ctx.outDir}/workflow.js. Write nothing else, and change no source.

Read ${PROMPT_FILE} ("README", "Output" and "Ground rules"), every ${ctx.outDir}/findings/*.json, ${ctx.outDir}/standards.md, ${ctx.outDir}/refactor-plan.md and ${ctx.outDir}/metrics.md.

Run facts from the workflow. Use them for scope, method, counts, and coverage and limitations:
${facts}

Previous review: look for docs/reviews/review-*/findings/*.json in folders older than this one. If one exists, compare by area, title and file, and report resolved, persisting and new findings. Otherwise, say this is the first review.

Keep the executive summary to five to eight bullets a maintainer can act on. Link the top recommendations to refactor-plan.md items and to findings. Build the scorecard from the scores in findings/*.json: areas in one table and lenses in another, with a dash where a dimension was not scored. State plainly that the review is static, that the metrics come from tools, and that it is not runtime, H1 or product acceptance evidence.`
}

function checkPrompt(ctx, facts) {
  return `Check the finished review in ${ctx.outDir} for completeness and correctness, and fix mechanical problems. Edit only files inside ${ctx.outDir}, and change no source.

Read ${PROMPT_FILE} ("Method" step 6, "Finding format" and "README").

1. Run this link and ID checker. Fix every problem it reports: broken relative links, missing anchors, line numbers past the end of a file, and finding IDs that no findings/*.json defines.
\`\`\`sh
${LINK_CHECKER.split('__OUT__').join(ctx.outDir)}
\`\`\`
2. Check that every findings/*.json parses, and that each of these parts has both files: ${Object.keys(SPEC).join(', ')}.
3. Check that refactor-plan.md addresses every high finding in findings/*.json by an item, or defers it with a reason. Add a "Not yet planned" section listing any that are missing.
4. Check that standards.md covers every dimension in "Goal".
5. Check that the README scorecard matches the scores in findings/*.json, and that its counts match the findings files.
6. Add any remaining gap to the README's coverage and limitations section.
Run the checker again until it reports no problems, or only problems you explain.

Run facts:
${facts}

Return what you fixed and what remains.`
}

function summarize(ctx, outcomes) {
  const perPart = []
  const verificationGaps = []
  const coverageGaps = []
  const bySeverity = { high: 0, medium: 0, low: 0 }
  let kept = 0
  let rejected = 0
  const count = (key, counts, rejectedCount, carried) => {
    for (const level of SEVERITIES) bySeverity[level] += counts[level]
    kept += counts.high + counts.medium + counts.low
    rejected += rejectedCount
    const spec = SPEC[key]
    perPart.push({ key, kind: spec ? spec.kind : 'unknown', files: (ctx.assigned[key] || []).length, high: counts.high, medium: counts.medium, low: counts.low, rejected: rejectedCount, carried })
  }
  const note = (key, text) => {
    if (text && text.trim()) coverageGaps.push(`${key}: ${text.trim()}`)
  }
  for (const outcome of outcomes) {
    outcome.group.forEach((key, index) => {
      const entry = outcome.entries[index]
      if (!entry) {
        verificationGaps.push(`${key}: no review came back`)
        return
      }
      if (entry.kind === 'verified') {
        count(key, entry.state, entry.state.rejected, true)
        note(key, entry.state.notCovered)
        return
      }
      const part = outcome.verified ? outcome.verified.areas.find((area) => area.key === key) : undefined
      if (!part) {
        verificationGaps.push(`${key}: reviewed but not verified, so it has no findings files`)
        return
      }
      const counts = { high: 0, medium: 0, low: 0 }
      for (const finding of part.kept) counts[finding.severity] += 1
      count(key, counts, part.rejected.length, false)
      if (entry.kind === 'saved') {
        note(key, entry.state.notCovered)
        return
      }
      note(key, entry.review.notCovered)
      const unread = (ctx.assigned[key] || []).filter((file) => !entry.review.filesRead.some((read) => read === file || read.endsWith('/' + file)))
      if (unread.length) coverageGaps.push(`${key}: not reported as read: ${unread.join(', ')}`)
    })
  }
  return { kept, rejected, bySeverity, perPart, verificationGaps, coverageGaps }
}

function buildFacts(ctx, summary, notes) {
  const carried = summary.perPart.filter((part) => part.carried).map((part) => part.key)
  return [
    `- Timestamp ${ctx.timestamp}. Revision ${ctx.revision}. ${ctx.dirtyFiles} paths were modified or untracked when this invocation started; the review read tracked files as they were on disk.`,
    `- ${ctx.files.length} in-scope tracked files in ${AREAS.length} areas, plus ${SWEEPS.length} cross-cutting lenses. Files no area claimed: ${ctx.unassigned.length ? ctx.unassigned.join(', ') : 'none'}.`,
    `- A full run plans 1 measure, ${AREAS.length + SWEEPS.length} reviewers, ${GROUPS.length} verifiers, 3 writers and 1 checker. Agents this invocation started before the README: ${counters.agents}, of which retries: ${counters.retries}.`,
    carried.length
      ? `- Resumed: ${carried.length} parts were verified by an earlier invocation and kept as written (${carried.join(', ')}). For those parts, coverage comes from their notCovered notes.`
      : '- Not resumed: every part was reviewed and verified in this invocation.',
    `- Verified findings: ${summary.kept} kept (${summary.bySeverity.high} high, ${summary.bySeverity.medium} medium, ${summary.bySeverity.low} low), ${summary.rejected} rejected or merged.`,
    '- Per part, kept high/medium/low and rejected:',
    ...summary.perPart.map((part) => `  - ${part.key} (${part.kind}${part.kind === 'area' ? `, ${part.files} files` : ''}): ${part.high}/${part.medium}/${part.low}, rejected ${part.rejected}`),
    `- Verification gaps: ${summary.verificationGaps.length ? summary.verificationGaps.join('; ') : 'none'}.`,
    `- Reviewer coverage notes: ${summary.coverageGaps.length ? summary.coverageGaps.join('; ') : 'none'}.`,
    `- Measurement problems: ${ctx.toolProblems || 'none'}.`,
    ...notes,
  ].join('\n')
}

// ---------------------------------------------------------------- run

checkConfiguration()

phase('Measure')
const requested = args && typeof args.timestamp === 'string' && /^\d{4}(-\d{2}){5}$/.test(args.timestamp) ? args.timestamp : ''
if (args && args.timestamp && !requested) log(`Ignoring timestamp "${args.timestamp}": expected yyyy-mm-dd-hh-mm-ss.`)
const resume = Boolean(args && args.resume === true)
const extraNotes = args && Array.isArray(args.notes) ? args.notes.filter((item) => typeof item === 'string').map((item) => `- ${item}`) : []
if (resume && !requested) throw new Error('Resuming needs the timestamp of the run to continue: {"timestamp": "yyyy-mm-dd-hh-mm-ss", "resume": true}.')

// Per part, what a resumed run found on disk. Empty for a fresh run.
const partState = {}
let measured
if (resume) {
  const inventory = await once(inventoryPrompt(requested), { label: 'inventory', phase: 'Measure', schema: INVENTORY_SCHEMA, effort: 'low' })
  if (!inventory) throw new Error('The inventory step returned nothing, so nothing resumed.')
  if (inventory.stop) throw new Error(`The inventory step stopped the run: ${inventory.stop}`)
  for (const part of inventory.parts) if (SPEC[part.key]) partState[part.key] = part
  const states = Object.values(partState)
  const verifiedCount = states.filter((part) => part.verified).length
  const savedCount = states.filter((part) => !part.verified && part.savedReview).length
  log(`Resuming ${inventory.outDir}. Parts already verified: ${verifiedCount}. Saved reviews to verify: ${savedCount}. Parts to review: ${Object.keys(SPEC).length - verifiedCount - savedCount}.`)
  if (inventory.toolProblems) log(`Inventory notes: ${inventory.toolProblems}`)
  measured = { ...inventory, fileMetrics: [], summary: '' }
} else {
  measured = await once(measurePrompt(requested), { label: 'measure', phase: 'Measure', schema: MEASURE_SCHEMA, effort: 'medium' })
  if (!measured) throw new Error('The measure step returned nothing, so no review started.')
  if (measured.stop) throw new Error(`The measure step stopped the run: ${measured.stop}`)
}
if (requested && measured.timestamp !== requested) throw new Error(`The run used ${measured.timestamp}, not the requested ${requested}.`)
if (measured.outDir !== `docs/reviews/review-${measured.timestamp}`) throw new Error(`Unexpected output folder: ${measured.outDir}`)
if (!measured.files.length) throw new Error('No in-scope files were listed.')

const { assigned, unassigned } = assignFiles(measured.files)
const ctx = { ...measured, assigned, unassigned }
log(`${measured.files.length} files at ${measured.revision.slice(0, 12)}. Writing ${measured.outDir}.`)
log(AREAS.map((spec) => `${spec.key} ${assigned[spec.key].length}`).join(', '))
for (const spec of AREAS) if (!assigned[spec.key].length) log(`Area ${spec.key} received no files.`)
if (unassigned.length) log(`No area claimed: ${unassigned.join(', ')}`)

phase('Review')
// Stage 1 settles each part: already verified on disk, a saved review to verify, or a new review.
// Stage 2 verifies whatever is not yet verified.
const outcomes = await pipeline(
  GROUPS,
  (group) => parallel(group.map((key) => async () => {
    const state = partState[key]
    if (state && state.verified) return { key, kind: 'verified', state }
    if (state && state.savedReview) return { key, kind: 'saved', file: state.savedReview, state }
    const review = await once(reviewPrompt(SPEC[key], ctx), { label: `review:${key}`, phase: 'Review', schema: REVIEW_SCHEMA })
    return review ? { key, kind: 'fresh', review: withIds(SPEC[key], review) } : null
  })),
  (entries, group) => {
    const missing = group.filter((_, index) => !entries[index])
    if (missing.length) log(`No review came back for ${missing.join(', ')}.`)
    const todo = entries.filter((entry) => entry && entry.kind !== 'verified')
    if (!todo.length) return { group, entries, verified: null }
    return once(verifyPrompt(todo, ctx), { label: `verify:${todo.map((entry) => entry.key).join('+')}`, phase: 'Verify', schema: VERIFY_SCHEMA })
      .then((verified) => ({ group, entries, verified }))
  },
)

const summary = summarize(ctx, outcomes.filter(Boolean))
if (outcomes.some((outcome) => !outcome)) log('A verification group failed before it returned; its parts have no findings files.')
log(`Verified: ${summary.kept} kept (${summary.bySeverity.high} high, ${summary.bySeverity.medium} medium, ${summary.bySeverity.low} low), ${summary.rejected} rejected or merged.`)
if (summary.verificationGaps.length) log(`Verification gaps: ${summary.verificationGaps.join('; ')}`)

phase('Synthesize')
// The writers read the findings files from disk. The digest tells them which parts exist, so a
// part that failed verification is named as missing instead of silently left out.
const digest = summary.perPart.map((part) => `${part.key} ${part.high}/${part.medium}/${part.low}`).join(', ') || 'none'
const [standards, plan] = await parallel([
  () => once(standardsPrompt(ctx, digest), { label: 'write:standards', phase: 'Synthesize' }),
  () => once(planPrompt(ctx, digest), { label: 'write:refactor-plan', phase: 'Synthesize' }),
])
const writerNotes = []
if (!standards) writerNotes.push('- standards.md was not written: its writer failed.')
if (!plan) writerNotes.push('- refactor-plan.md was not written: its writer failed.')
const facts = buildFacts(ctx, summary, [...writerNotes, ...extraNotes])
const readme = await once(readmePrompt(ctx, facts), { label: 'write:readme', phase: 'Synthesize' })
if (!readme) log('The README writer failed; README.md may be missing.')

phase('Check')
const check = await once(checkPrompt(ctx, facts), { label: 'check', phase: 'Check', schema: CHECK_SCHEMA })

return {
  outDir: ctx.outDir,
  revision: ctx.revision,
  resumed: resume,
  agentsStarted: counters.agents,
  retries: counters.retries,
  kept: summary.kept,
  rejected: summary.rejected,
  bySeverity: summary.bySeverity,
  perPart: summary.perPart,
  verificationGaps: summary.verificationGaps,
  coverageGaps: summary.coverageGaps,
  unassigned,
  check,
}
