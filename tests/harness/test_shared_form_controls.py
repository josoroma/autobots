"""US-11.11: a form control comes from the shared components, including on screens only a state reaches."""
from __future__ import annotations

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
RAW = re.compile(r'<(input|select|textarea)\b')
SHARED = ROOT / 'apps/web/components/ui/field.tsx'


class SharedFormControls(unittest.TestCase):
    def test_no_screen_draws_a_raw_control(self) -> None:
        files = [path for folder in ('apps/web/components', 'apps/web/app') for path in (ROOT / folder).rglob('*.tsx')]
        self.assertGreater(len(files), 20, 'the screens have moved, so this no longer checks them')
        self.assertIn(SHARED, files)
        found = [str(path.relative_to(ROOT)) for path in files if path != SHARED and RAW.search(path.read_text())]
        self.assertEqual(found, [])

    def test_the_check_would_see_one(self) -> None:
        self.assertIsNotNone(RAW.search('<input id="x" />'))
        self.assertIsNone(RAW.search('<Input id="x" />'))


if __name__ == '__main__':
    unittest.main()
