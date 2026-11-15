"""R-68: arbitrary pixel classes in the web source only ever decrease.

A class such as `text-[13px]` or `px-[18px]` bypasses the theme's type, radius and spacing steps
(PRD-Design-System DS-03, XWEB-12, WSHL-13). Type sizes and radii have named steps in
apps/web/app/globals.css, so neither may use a pixel value at all. Any other pixel class may appear
in a file at most the number of times recorded here. A file that drops below its count fails too,
until the count is lowered, so a removed class can't quietly come back.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / 'apps/web'
FOLDERS = ('app', 'components', 'lib')
# A utility with an arbitrary value holding a pixel length, such as `-left-[19.5px]`.
PIXEL_CLASS = re.compile(r'([a-z][a-z0-9-]*)-\[([^\]\s"\'`]*?\d(?:\.\d+)?px[^\]\s"\'`]*)\]')

# Each file's count of arbitrary pixel classes. Lower a count when a file loses one; never raise it.
# Pixel paddings stay fixed: a spacing step would also tighten under compact density (PRD-Studio
# SE-03, XWEB-12), which is a visible change.
BASELINE = {
    'app/page.tsx': 1,
    'components/app-shell.tsx': 1,
    'components/appearance-control.tsx': 10,
    'components/expert-editor/expert-editor.tsx': 1,
    'components/experts/expert-card.tsx': 1,
    'components/model-policy/approved-models.tsx': 1,
    'components/model-policy/policy-form.tsx': 1,
    'components/provider-settings/connection-bar.tsx': 4,
    'components/provider-settings/provider-settings-panel.tsx': 1,
    'components/provider-settings/route-qualifications.tsx': 1,
    'components/runs/list/run-rows.tsx': 1,
    'components/runs/workspace/timeline-section.tsx': 1,
    'components/tools/tool-group-section.tsx': 3,
    'components/tools/tool-overview.tsx': 1,
    'components/ui/section.tsx': 2,
    'components/ui/segmented-control.tsx': 1,
    'components/ui/status-dot.tsx': 1,
    'components/workflow-editor/workflow-editor.tsx': 1,
    'components/workflow-monitor.tsx': 1,
}


def pixel_classes(web: Path) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for folder in FOLDERS:
        for path in sorted((web / folder).rglob('*.ts*')):
            if path.suffix not in ('.ts', '.tsx'):
                continue
            classes = [f'{utility}-[{value}]' for utility, value in PIXEL_CLASS.findall(path.read_text())]
            if classes:
                found[path.relative_to(web).as_posix()] = classes
    return found


def drift(found: dict[str, int], baseline: dict[str, int]) -> list[str]:
    problems = []
    for name in sorted(found.keys() | baseline.keys()):
        now, allowed = found.get(name, 0), baseline.get(name, 0)
        if now > allowed:
            problems.append(f'{name}: {now} arbitrary pixel classes, more than its {allowed}')
        elif now < allowed:
            problems.append(f'{name}: {now} arbitrary pixel classes, so lower its baseline from {allowed}')
    return problems


def unnamed_steps(found: dict[str, list[str]]) -> list[str]:
    return [f'{name}: {cls}' for name, classes in found.items() for cls in classes
            if cls.startswith(('text-[', 'rounded-['))
            or re.match(r'rounded-[a-z]{1,2}-\[', cls)]


class ArbitraryPixelClasses(unittest.TestCase):
    def test_no_file_holds_more_than_its_baseline_or_less_than_recorded(self) -> None:
        self.assertGreater(len(list((WEB / 'components').rglob('*.tsx'))), 20, 'the screens have moved')
        found = {name: len(classes) for name, classes in pixel_classes(WEB).items()}
        self.assertEqual(drift(found, BASELINE), [])

    def test_type_sizes_and_radii_use_the_named_steps(self) -> None:
        self.assertEqual(unnamed_steps(pixel_classes(WEB)), [])

    def test_the_pattern_sees_pixel_values_only(self) -> None:
        seen = [
            'text-[12.5px]', 'md:text-[44px]', 'rounded-[10px]', '-left-[19.5px]',
            'has-[:checked]:ring-[3px]', 'md:grid-cols-[minmax(0,240px)_minmax(0,1fr)]',
        ]
        for text in seen:
            self.assertEqual(len(PIXEL_CLASS.findall(text)), 1, text)
        unseen = ['text-meta', 'rounded-lg', 'w-[calc(100%-2rem)]', 'tracking-[-0.015em]',
                  'max-h-[min(92vh,60rem)]', 'leading-[1.1]', 'has-checked:ring-3']
        for text in unseen:
            self.assertEqual(PIXEL_CLASS.findall(text), [], text)

    def test_the_checks_fail_when_they_should(self) -> None:
        self.assertEqual(drift({'a.tsx': 2}, {'a.tsx': 2}), [])
        self.assertEqual(len(drift({'a.tsx': 3}, {'a.tsx': 2})), 1)
        self.assertEqual(len(drift({'a.tsx': 1}, {'a.tsx': 2})), 1)
        self.assertEqual(len(drift({'new.tsx': 1}, {})), 1)
        found = {'a.tsx': ['text-[13px]', 'rounded-tl-[7px]', 'rounded-[10px]', 'px-[18px]']}
        self.assertEqual(len(unnamed_steps(found)), 3)


if __name__ == '__main__':
    unittest.main()
