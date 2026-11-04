"""Behavior tests for binding verdicts to a story's changed files; offline, no services."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "story_manifest.py"
STORY = "US-1.3"


class StoryManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        (self.root / ".gitignore").write_text("ignored.txt\n")
        (self.root / "app.py").write_text("base\n")
        self.git("init", "-q")
        self.commit()

    def git(self, *arguments: str) -> None:
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", *arguments], check=True)

    def commit(self) -> None:
        self.git("add", "-A")
        self.git("commit", "-qm", "fixture")

    def run_command(self, command: str, story: str = STORY) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(SCRIPT), command, story, "--project-root", str(self.root)], capture_output=True, text=True, check=False)

    def write(self, name: str, text: str = "x\n") -> None:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def captured(self) -> None:
        self.write("app.py", "implemented\n")
        self.write("web/new.ts", "new\n")
        result = self.run_command("capture")
        self.assertEqual(0, result.returncode, result.stderr)

    def assert_stale(self, expected: str) -> None:
        result = self.run_command("compare")
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn(expected, result.stderr)

    def test_unchanged_tree_matches(self) -> None:
        self.captured()
        result = self.run_command("compare")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("2 files", result.stdout)

    def test_manifest_covers_tracked_and_untracked_product_files(self) -> None:
        self.captured()
        manifest = json.loads((self.root / "docs/engineering/evidence/US-1.3/reviewed-manifest.json").read_text())
        self.assertEqual({"app.py", "web/new.ts"}, set(manifest["files"]))
        self.assertEqual(64, len(manifest["fingerprint"]))

    def test_any_product_change_after_capture_is_stale(self) -> None:
        cases = {
            "changed: app.py": lambda: self.write("app.py", "edited after review\n"),
            "changed: web/new.ts": lambda: self.write("web/new.ts", "edited after review\n"),
            "added: web/late.ts": lambda: self.write("web/late.ts"),
            "added: pnpm-lock.yaml": lambda: self.write("pnpm-lock.yaml"),
            "added: SPECS.md": lambda: self.write("SPECS.md"),
            "added: openspec/changes/c/tasks.md": lambda: self.write("openspec/changes/c/tasks.md"),
            "removed: web/new.ts": lambda: (self.root / "web/new.ts").unlink(),
        }
        for expected, mutate in cases.items():
            with self.subTest(expected):
                self.captured()
                mutate()
                self.assert_stale(expected)
                for extra in ("web/late.ts", "pnpm-lock.yaml", "SPECS.md", "openspec/changes/c/tasks.md"):
                    (self.root / extra).unlink(missing_ok=True)

    def test_deleted_tracked_file_is_bound_and_restoring_it_is_stale(self) -> None:
        (self.root / "app.py").unlink()
        self.assertEqual(0, self.run_command("capture").returncode)
        self.assertEqual(0, self.run_command("compare").returncode)
        self.write("app.py", "base\n")
        self.assert_stale("removed: app.py")

    def test_a_commit_after_capture_is_stale(self) -> None:
        self.captured()
        self.commit()
        self.assert_stale("removed: app.py")

    def test_records_written_after_review_are_excluded(self) -> None:
        self.captured()
        for name in (
            "docs/engineering/work-items/US-1.3.md", "docs/engineering/evidence/US-1.3/summary.md",
            "openspec/delivery/goal.md", "openspec/changes/c/review.md", "openspec/changes/c/test-report.md",
            "openspec/changes/c/status.md", "openspec/changes/c/completion.md", "openspec/changes/c/history/review-r1.md",
        ):
            self.write(name)
        result = self.run_command("compare")
        self.assertEqual(0, result.returncode, result.stderr)

    def test_another_storys_records_and_ignored_files(self) -> None:
        self.captured()
        self.write("ignored.txt")
        self.assertEqual(0, self.run_command("compare").returncode)
        self.write("docs/engineering/work-items/US-1.2.md")
        self.assert_stale("added: docs/engineering/work-items/US-1.2.md")

    def test_nested_repository_is_refused_not_hashed_as_a_constant(self) -> None:
        self.write("vendored/code.py")
        subprocess.run(["git", "-C", str(self.root / "vendored"), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(self.root / "vendored"), "-c", "user.name=f", "-c", "user.email=f@example.invalid", "commit", "-q", "--allow-empty", "-m", "x"], check=True)
        result = self.run_command("capture")
        self.assertEqual(2, result.returncode, result.stdout)
        self.assertIn("directory entry", result.stderr)
        self.assertFalse((self.root / "docs/engineering/evidence/US-1.3").exists())

    def test_executable_bit_change_is_stale(self) -> None:
        self.captured()
        (self.root / "web/new.ts").chmod(0o755)
        self.assert_stale("changed: web/new.ts")

    def test_staged_rename_reports_both_paths(self) -> None:
        self.git("mv", "app.py", "renamed.py")
        self.assertEqual(0, self.run_command("capture").returncode)
        manifest = json.loads((self.root / "docs/engineering/evidence/US-1.3/reviewed-manifest.json").read_text())
        self.assertEqual({"app.py", "renamed.py"}, set(manifest["files"]))

    def test_edited_or_foreign_manifest_fails_compare(self) -> None:
        self.captured()
        path = self.root / "docs/engineering/evidence/US-1.3/reviewed-manifest.json"
        original = json.loads(path.read_text())
        edited = json.loads(path.read_text())
        edited["files"]["app.py"] = "0" * 64
        path.write_text(json.dumps(edited))
        self.assertIn("inconsistent", self.run_command("compare").stderr)
        path.write_text(json.dumps({**original, "story": "US-1.2"}))
        self.assertIn("inconsistent", self.run_command("compare").stderr)
        for malformed in ("[]", json.dumps({**original, "files": []})):
            path.write_text(malformed)
            result = self.run_command("compare")
            self.assertNotEqual(0, result.returncode)
            self.assertNotIn("Traceback", result.stderr)

    def test_capture_refuses_an_empty_change(self) -> None:
        result = self.run_command("capture")
        self.assertEqual(1, result.returncode)
        self.assertIn("no changed files", result.stderr)
        self.assertFalse((self.root / "docs/engineering/evidence/US-1.3").exists())

    def test_compare_without_a_capture_fails(self) -> None:
        result = self.run_command("compare")
        self.assertEqual(2, result.returncode)

    def test_story_id_cannot_escape_the_evidence_directory(self) -> None:
        for story in ("../../etc", "US-1", "US-1.1/..", "EPIC-1"):
            with self.subTest(story):
                self.assertEqual(2, self.run_command("capture", story).returncode)


if __name__ == "__main__":
    unittest.main()
