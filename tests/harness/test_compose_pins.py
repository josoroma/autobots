"""The synthetic stack runs the install overlay's database and storage images, and the overlay keeps every init
script upstream mounts (refactor plan R-65, SQLI-15, SQLI-19). Read from the files; no Docker runs here."""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import supabase_stack  # noqa: E402

IMAGE = re.compile(r'^\s+image:\s*(\S+)$', re.MULTILINE)


def images(path: str) -> list[str]:
    return IMAGE.findall((ROOT / path).read_text())


class Pins(unittest.TestCase):
    def test_the_synthetic_stack_runs_the_overlays_digests(self) -> None:
        """DH-07: the same pinned family for integration coverage. `make images` pulls exactly these."""
        disposable = images('infra/disposable/compose.yaml')
        self.assertEqual(len(disposable), 2)
        self.assertLessEqual(set(disposable), set(images('infra/supabase/compose.overlay.yaml')))
        for image in disposable:
            with self.subTest(image):
                self.assertRegex(image, r'@sha256:[0-9a-f]{64}$')

    def test_every_upstream_init_script_survives_the_overlays_list(self) -> None:
        """The overlay restates the db volumes to make them read-only, so a script upstream adds must be added there too."""
        overlay = (ROOT / 'infra/supabase/compose.overlay.yaml').read_text()
        mounted = {line.strip().removeprefix('- ').split(':')[1] for line in overlay.splitlines() if line.strip().startswith('- ./volumes/db/')}
        self.assertEqual(supabase_stack.upstream_init_targets(ROOT) - mounted, frozenset())

    def test_no_resource_limit_was_guessed(self) -> None:
        """Limits follow a measurement (PRD-Local-Mac-Deployment), which doesn't exist, and an overlay edit makes existing
        backups refuse to restore (local_backup.compose_hashes), so none is set until one is measured (SQLI-19)."""
        overlay = (ROOT / 'infra/supabase/compose.overlay.yaml').read_text()
        self.assertNotRegex(overlay, r'\b(mem_limit|cpus|deploy):')


if __name__ == '__main__':
    unittest.main()
