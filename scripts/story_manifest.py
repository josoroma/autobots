#!/usr/bin/env python3
"""Record what a story's review and test verdicts covered, and detect later changes.

The harness fingerprint covers repository tooling, not application source or locks, so
it cannot show that reviewed code is still the code being archived. `capture` hashes
each changed tracked and untracked non-ignored file before review. `compare` recomputes
that set before archive and fails on any difference. Records written after review are
excluded. Git-ignored files are not covered. A recapture is detectable only because
verdicts must state the fingerprint. Run from a story-bounded working tree.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

STORY = re.compile(r"US-[1-9]\d*\.[1-9]\d*")
CHANGE_RECORD = re.compile(r"openspec/changes/[^/]+/(?:review\.md|test-report\.md|status\.md|completion\.md|history/.*)")


def is_record(path: str, story: str) -> bool:
    return (path == f"docs/engineering/work-items/{story}.md"
            or path.startswith((f"docs/engineering/evidence/{story}/", "openspec/delivery/"))
            or CHANGE_RECORD.fullmatch(path) is not None)


def git_paths(root: Path, *arguments: str) -> list[str]:
    result = subprocess.run(["git", "-C", str(root), *arguments, "-z"], capture_output=True, check=False)
    if result.returncode:
        raise ValueError(f"git {arguments[0]} failed: {result.stderr.decode(errors='replace').strip()}")
    return [item for item in result.stdout.decode().split("\0") if item]


def digest(path: Path) -> str:
    if path.is_symlink():
        return "symlink:" + hashlib.sha256(os.readlink(path).encode()).hexdigest()
    if not path.exists():
        return "absent"
    if path.is_dir():
        raise ValueError(f"cannot bind directory entry {path.name} (nested repository, submodule or file replaced by a directory); its contents would go unchecked")
    return hashlib.sha256(path.read_bytes()).hexdigest() + (":executable" if os.access(path, os.X_OK) else "")


def current_files(root: Path, story: str) -> dict[str, str]:
    changed = git_paths(root, "diff", "--no-renames", "--name-only", "HEAD") + git_paths(root, "ls-files", "--others", "--exclude-standard")
    return {path: digest(root / path) for path in sorted(set(changed)) if not is_record(path, story)}


def fingerprint(files: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def manifest_path(root: Path, story: str) -> Path:
    return root / "docs/engineering/evidence" / story / "reviewed-manifest.json"


def capture(root: Path, story: str) -> int:
    files = current_files(root, story)
    if not files:
        print(f"ERROR: {story} has no changed files to bind; nothing can be reviewed.", file=sys.stderr)
        return 1
    path = manifest_path(root, story)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": 1, "story": story, "fingerprint": fingerprint(files),
                                "files": files}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"PASS: capture: {story}: {len(files)} files, fingerprint {fingerprint(files)}")
    return 0


def compare(root: Path, story: str) -> int:
    manifest = json.loads(manifest_path(root, story).read_text(encoding="utf-8"))
    reviewed = manifest["files"]
    if manifest["story"] != story or manifest["fingerprint"] != fingerprint(reviewed):
        print(f"FAIL: compare: {story}: the manifest is inconsistent with its own story or fingerprint", file=sys.stderr)
        return 1
    current = current_files(root, story)
    differences = [f"{kind}: {path}" for kind, paths in (
        ("added", current.keys() - reviewed.keys()),
        ("removed", reviewed.keys() - current.keys()),
        ("changed", {path for path in current.keys() & reviewed.keys() if current[path] != reviewed[path]}),
    ) for path in sorted(paths)]
    if differences:
        print(f"FAIL: compare: {story}: verdicts are stale for the current files", file=sys.stderr)
        for difference in differences:
            print(f"  {difference}", file=sys.stderr)
        return 1
    print(f"PASS: compare: {story}: {len(current)} files match the reviewed manifest")
    return 0


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < (3, 12):
        print("ERROR: Python 3.12+ is required; use the qualified python3.12 interpreter.", file=sys.stderr)
        return 2
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("capture", "compare"))
    parser.add_argument("story", help="story ID, for example US-1.1")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    if not STORY.fullmatch(args.story):
        print(f"ERROR: not a story ID: {args.story}", file=sys.stderr)
        return 2
    try:
        root = args.project_root.resolve(strict=True)
        return (capture if args.command == "capture" else compare)(root, args.story)
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, AttributeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
