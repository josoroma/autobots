"""Behavior tests for the offline SPECS contract; no services or paid calls."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "specs.py"
MODULE_SPEC = importlib.util.spec_from_file_location("autobots_specs", SCRIPT)
assert MODULE_SPEC is not None and MODULE_SPEC.loader is not None
specs = importlib.util.module_from_spec(MODULE_SPEC)
sys.modules[MODULE_SPEC.name] = specs
MODULE_SPEC.loader.exec_module(specs)


def story(
    identifier: str = "US-1.1", *, status: str = "READY",
    dependency: str = "None.", question: str = "None.", done: bool = False,
    source: str = "[Provider requirements](PRD.md#mp-01), MP-A01.",
) -> str:
    return f"""### {identifier}: Validate a bounded change

Status: {status}

As a contributor
I want reproducible validation
So that invalid work cannot silently pass.

Source:
- {source}

Acceptance Criteria:

```gherkin
Scenario: Reject malformed work
  Given a fixture violates a required contract
  When the validation command examines it
  Then the command exits unsuccessfully
  And the error names the violated contract
```

Dependencies:
- {dependency}

Tasks:
- [{'x' if done else ' '}] Implement the bounded contract
- [{'x' if done else ' '}] Verify positive and negative fixtures

Open Questions:
- {question}
"""


def document(*stories: str) -> str:
    return """# SPECS — fixture

CODEBASE Context: absent

## Product Context

Preserve this authored context and SP-001 cross-reference verbatim.

# EPIC-1: Engineering contracts

""" + "\n".join(stories or [story()])


class SpecsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.path = self.root / "SPECS.md"
        (self.root / "PRD.md").write_text("# PRD\n\n## MP-01\n\nMP-A01: validate.\n", encoding="utf-8")

    def errors(self, text: str, *, navigation: bool = False) -> list[str]:
        return [issue.message for issue in specs.validate_text(text, self.root, self.path, navigation=navigation).issues]

    def render(self, text: str) -> str:
        parsed = specs.validate_text(text, self.root, self.path, navigation=False)
        self.assertEqual([], parsed.issues)
        return specs.render_text(text, parsed)

    def test_render_then_validate_and_idempotent_render(self) -> None:
        original = document()
        rendered = self.render(original)
        self.assertEqual([], self.errors(rendered, navigation=True))
        self.assertEqual(rendered, self.render(rendered))
        self.assertEqual(original[original.index("## Product Context"):], rendered[rendered.index("## Product Context"):])
        self.assertEqual(original[:original.index("## Product Context")], rendered[:rendered.index("## Table of Contents")])
        self.assertIn("| US-1.1#1 | Implement the bounded contract | TODO | US-1.1 |", rendered)

    def test_missing_and_stale_navigation_are_failures(self) -> None:
        self.assertTrue(any("stale" in issue for issue in self.errors(document(), navigation=True)))
        rendered = self.render(document())
        stale = rendered.replace("| US-1.1 | Validate a bounded change | READY", "| US-1.1 | Validate a bounded change | DONE")
        self.assertTrue(any("stale" in issue for issue in self.errors(stale, navigation=True)))

    def test_preserve_crlf_and_four_backtick_global_example(self) -> None:
        example = "````markdown\n# EPIC-99: Example only\n### US-99.1: Example only\n```gherkin\nScenario: Example\n```\n````\n\n"
        original = document().replace("# EPIC-1:", example + "# EPIC-1:").replace("\n", "\r\n")
        rendered = self.render(original)
        self.assertEqual(1, len(specs.parse_document(rendered, self.root, self.path).epics))
        self.assertEqual(original[original.index("## Product Context"):], rendered[rendered.index("## Product Context"):])
        self.assertNotIn("\n", rendered.replace("\r\n", ""))

    def test_four_backtick_gherkin_is_accepted(self) -> None:
        original = document().replace("```gherkin", "````gherkin").replace("\n```\n", "\n````\n")
        self.assertEqual([], self.errors(original))

    def test_duplicate_and_malformed_ids_rejected(self) -> None:
        self.assertTrue(any("duplicate ID" in issue for issue in self.errors(document(story(), story()))))
        for invalid in ("US-01.1", "US-1", "US-1.0", "US-one.1"):
            with self.subTest(invalid=invalid):
                self.assertTrue(any("malformed" in issue for issue in self.errors(document(story(invalid)))))

    def test_story_must_match_enclosing_epic(self) -> None:
        self.assertTrue(any("does not belong" in issue for issue in self.errors(document(story("US-2.1")))))

    def test_dependency_cycle_rejected(self) -> None:
        original = document(
            story(status="BLOCKED", dependency="US-1.2"),
            story("US-1.2", status="BLOCKED", dependency="US-1.1"),
        )
        self.assertTrue(any("dependency cycle" in issue for issue in self.errors(original)))

    def test_self_dependency_rejected(self) -> None:
        self.assertTrue(any("dependency cycle" in issue for issue in self.errors(document(story(status="BLOCKED", dependency="US-1.1")))))

    def test_missing_dependency_rejected(self) -> None:
        self.assertTrue(any("missing US-9.9" in issue for issue in self.errors(document(story(status="BLOCKED", dependency="US-9.9")))))

    def test_ready_requires_done_dependencies(self) -> None:
        invalid = document(story(), story("US-1.2", dependency="US-1.1"))
        self.assertTrue(any("requires all dependencies DONE" in issue for issue in self.errors(invalid)))
        valid = document(story(status="DONE", done=True), story("US-1.2", dependency="US-1.1 is delivered."))
        self.assertEqual([], self.errors(valid))

    def test_external_dependency_blocks_ready(self) -> None:
        invalid = document(story(dependency="External: operator decision"))
        self.assertTrue(any("External dependency" in issue for issue in self.errors(invalid)))
        valid = document(story(status="BLOCKED", dependency="External: operator decision"))
        rendered = self.render(valid)
        self.assertEqual(1, rendered.count("-.->"))
        self.assertIn("External: operator decision", rendered)

    def test_only_declared_dependencies_have_dotted_edges(self) -> None:
        original = document(story(status="DONE", done=True), story("US-1.2", dependency="US-1.1"))
        original += "\n# EPIC-2: Another capability\n\n" + story("US-2.1", status="BLOCKED", dependency="US-1.2")
        rendered = self.render(original)
        self.assertEqual(2, rendered.count("-.->"))
        self.assertIn("US_1_1 -.-> US_1_2", rendered)
        self.assertIn("US_1_2 -.-> US_2_1", rendered)
        self.assertEqual(3, rendered.count("```mermaid"))

    def test_missing_then_and_out_of_order_steps_rejected(self) -> None:
        missing = document().replace("  Then the command exits unsuccessfully\n", "")
        self.assertTrue(any("ordered Given, When, Then" in issue for issue in self.errors(missing)))
        wrong_order = document().replace("Given a fixture", "When a fixture").replace("When the validation", "Given the validation")
        self.assertTrue(any("ordered Given, When, Then" in issue for issue in self.errors(wrong_order)))

    def test_each_scenario_must_be_complete(self) -> None:
        original = document().replace("  And the error names the violated contract", "\nScenario: Incomplete second case\n  Given another fixture\n  When it is checked")
        self.assertTrue(any("Incomplete second case" in issue for issue in self.errors(original)))

    def test_acceptance_prose_cannot_bypass_gherkin(self) -> None:
        original = document().replace("Acceptance Criteria:\n", "Acceptance Criteria:\n- It should work.\n")
        self.assertTrue(any("only fenced Gherkin" in issue for issue in self.errors(original)))

    def test_unclosed_fence_rejected(self) -> None:
        self.assertTrue(any("unclosed" in issue for issue in self.errors(document().replace("\n```\n", "\n"))))

    def test_required_field_and_invalid_status_rejected(self) -> None:
        self.assertTrue(any("missing Source" in issue for issue in self.errors(document().replace("Source:\n", "References:\n"))))
        self.assertTrue(any("invalid or missing Status" in issue for issue in self.errors(document(story(status="FINISHED")))))

    def test_article_an_and_optional_codebase_reference(self) -> None:
        (self.root / "CODEBASE.md").write_text("# CODEBASE\n\n## State\n", encoding="utf-8")
        original = document().replace("As a contributor", "As an operator").replace("Acceptance Criteria:\n", "Codebase Context:\n- [Current state](CODEBASE.md#state)\n\nAcceptance Criteria:\n")
        self.assertEqual([], self.errors(original))

    def test_fields_must_follow_the_upstream_order(self) -> None:
        original = document().replace("Dependencies:\n- None.\n\n", "").replace("Open Questions:", "Dependencies:\n- None.\n\nOpen Questions:")
        self.assertTrue(any("field order" in issue for issue in self.errors(original)))

    def test_open_questions_status_conflicts(self) -> None:
        self.assertTrue(any("unresolved Open Questions" in issue for issue in self.errors(document(story(question="Which policy is approved?")))))
        self.assertTrue(any("requires an Open Question" in issue for issue in self.errors(document(story(status="NEEDS CLARIFICATION")))))
        conflict = document(story(status="NEEDS CLARIFICATION", question="Conflict: source requirements disagree."))
        self.assertTrue(any("conflict requires BLOCKED" in issue for issue in self.errors(conflict)))
        self.assertEqual([], self.errors(document(story(status="BLOCKED", question="Conflict: source requirements disagree."))))

    def test_none_prefix_does_not_hide_a_conflict(self) -> None:
        original = document(story(question="None. Conflict: sources still disagree."))
        self.assertTrue(any("conflict requires BLOCKED" in issue for issue in self.errors(original)))

    def test_done_requires_completed_tasks(self) -> None:
        self.assertTrue(any("DONE with unfinished tasks" in issue for issue in self.errors(document(story(status="DONE")))))

    def test_source_must_exist_and_have_a_section(self) -> None:
        self.assertTrue(any("does not exist" in issue for issue in self.errors(document(story(source="[Missing](missing.md#section)")))))
        self.assertTrue(any("section/requirement" in issue for issue in self.errors(document(story(source="[PRD](PRD.md)")))))
        self.assertEqual([], self.errors(document(story(source="[PRD](PRD.md), MP-A01."))))

    def test_nonexistent_source_anchor_and_requirement_id_rejected(self) -> None:
        invalid_anchor = document(story(source="[PRD](PRD.md#invented-heading)"))
        invalid_id = document(story(source="[PRD](PRD.md), MP-A999."))
        self.assertTrue(any("'#invented-heading' does not exist" in issue for issue in self.errors(invalid_anchor)))
        self.assertTrue(any("'MP-A999' does not exist" in issue for issue in self.errors(invalid_id)))

    def test_source_html_ids_duplicate_headings_and_fenced_examples(self) -> None:
        (self.root / "PRD.md").write_text('# PRD\n\n## Repeated\n\n## Repeated\n\n<a id="explicit-anchor"></a>\n\n```markdown\n## Fake heading\n```\n', encoding="utf-8")
        for target in ("#repeated", "#repeated-1", "#explicit-anchor"):
            with self.subTest(target=target):
                self.assertEqual([], self.errors(document(story(source=f"[PRD](PRD.md{target})"))))
        self.assertTrue(any("does not exist" in issue for issue in self.errors(document(story(source="[PRD](PRD.md#fake-heading)")))))

    def test_source_cannot_read_configuration_file_as_requirement(self) -> None:
        (self.root / ".env").write_text("not-a-real-secret", encoding="utf-8")
        self.assertTrue(any("Markdown document" in issue for issue in self.errors(document(story(source="[Invalid](.env), MP-A01.")))))

    def test_numeric_section_and_setext_heading_references(self) -> None:
        (self.root / "PRD.md").write_text("# PRD\n\n## 6.2 Provider rules\n\nSupplement\n----------\n", encoding="utf-8")
        self.assertEqual([], self.errors(document(story(source="[PRD](PRD.md), §6.2."))))
        self.assertEqual([], self.errors(document(story(source="[PRD](PRD.md#supplement)"))))
        self.assertTrue(any("'§6.9' does not exist" in issue for issue in self.errors(document(story(source="[PRD](PRD.md), §6.9.")))))

    def test_remote_absolute_and_traversal_sources_rejected(self) -> None:
        outside = self.root.parent / f"{self.root.name}-outside.md"
        outside.write_text("external", encoding="utf-8")
        self.addCleanup(outside.unlink)
        for source in (
            f"[Outside](../{outside.name}#section)",
            f"[Outside](%2e%2e/{outside.name}#section)",
            f"[Absolute]({outside}#section)",
            "[Remote](https://example.com/source.md#section)",
        ):
            with self.subTest(source=source):
                self.assertTrue(self.errors(document(story(source=source))))

    def test_symlink_source_escape_rejected(self) -> None:
        outside = self.root.parent / f"{self.root.name}-outside.md"
        outside.write_text("external", encoding="utf-8")
        self.addCleanup(outside.unlink)
        (self.root / "link.md").symlink_to(outside)
        self.assertTrue(any("escapes project root" in issue for issue in self.errors(document(story(source="[Link](link.md#section)")))))

    def test_duplicate_or_misordered_navigation_rejected_without_mutation(self) -> None:
        rendered = self.render(document())
        for changed in (
            rendered.replace("## Work Item Status", "## Table of Contents"),
            rendered.replace("## Product Context", "## Unowned Section\n\nImportant text\n\n## Product Context"),
        ):
            with self.subTest(changed=changed[:60]):
                self.assertTrue(self.errors(changed, navigation=True))

    def test_cli_render_and_validate_are_offline_and_preserve_authored_body(self) -> None:
        original = document()
        self.path.write_text(original, encoding="utf-8")
        rendered = subprocess.run([sys.executable, str(SCRIPT), "render", "--project-root", str(self.root)], capture_output=True, text=True, check=False)
        self.assertEqual(0, rendered.returncode, rendered.stderr)
        updated = self.path.read_bytes()
        validated = subprocess.run([sys.executable, str(SCRIPT), "validate", "--project-root", str(self.root)], capture_output=True, text=True, check=False)
        self.assertEqual(0, validated.returncode, validated.stderr)
        self.assertEqual(updated, self.path.read_bytes())

    def test_cli_invalid_input_leaves_file_untouched(self) -> None:
        original = document().replace("  Then the command exits unsuccessfully\n", "")
        self.path.write_text(original, encoding="utf-8")
        result = subprocess.run([sys.executable, str(SCRIPT), "render", "--project-root", str(self.root)], capture_output=True, text=True, check=False)
        self.assertEqual(1, result.returncode)
        self.assertEqual(original, self.path.read_text(encoding="utf-8"))

    def promoted(self, text: str) -> list[str]:
        parsed = specs.validate_text(text, self.root, self.path, navigation=False)
        self.assertEqual([], parsed.issues)
        return specs.promote_text(text, parsed)[1]

    def test_promote_requires_every_declared_dependency_done(self) -> None:
        done = story(status="DONE", done=True)
        self.assertEqual(["US-1.2"], self.promoted(document(done, story("US-1.2", status="BLOCKED", dependency="US-1.1"))))
        partial = document(done, story("US-1.2", status="BLOCKED"), story("US-1.3", status="BLOCKED", dependency="US-1.1\n- US-1.2"))
        self.assertEqual([], self.promoted(partial))
        # One round only: promotion to READY does not satisfy a dependent story.
        chain = document(done, story("US-1.2", status="BLOCKED", dependency="US-1.1"), story("US-1.3", status="BLOCKED", dependency="US-1.2"))
        self.assertEqual(["US-1.2"], self.promoted(chain))

    def test_promote_leaves_human_decisions_blocked(self) -> None:
        done = story(status="DONE", done=True)
        cases = {
            "external": story("US-1.2", status="BLOCKED", dependency="US-1.1\n- External: paid qualification"),
            "question": story("US-1.2", status="BLOCKED", dependency="US-1.1", question="Which destination is first?"),
            "conflict": story("US-1.2", status="BLOCKED", dependency="US-1.1", question="Sources conflict on retries."),
            "undeclared": story("US-1.2", status="BLOCKED"),
            "clarification": story("US-1.2", status="NEEDS CLARIFICATION", dependency="US-1.1", question="Which one?"),
        }
        for name, blocked in cases.items():
            with self.subTest(name):
                self.assertEqual([], self.promoted(document(done, blocked)))

    def test_promote_refuses_a_dependency_line_with_trailing_prose(self) -> None:
        # The parser records only the first ID, so prose could hide a second blocker.
        done = story(status="DONE", done=True)
        for line in ("US-1.1 and US-1.3", "US-1.1 after External approval", "US-1.1 is delivered."):
            with self.subTest(line):
                self.assertEqual([], self.promoted(document(done, story("US-1.2", status="BLOCKED", dependency=line), story("US-1.3", status="BLOCKED"))))
        self.assertEqual(["US-1.2"], self.promoted(document(done, story("US-1.2", status="BLOCKED", dependency="US-1.1."))))

    def test_promote_only_touches_blocked_stories(self) -> None:
        done = story(status="DONE", done=True)
        for status in ("READY", "IN PROGRESS"):
            with self.subTest(status):
                self.assertEqual([], self.promoted(document(done, story("US-1.2", status=status, dependency="US-1.1"))))

    def test_change_line_is_valid_only_in_the_status_block(self) -> None:
        line = "Change: `openspec/changes/validate-a-bounded-change/`"
        self.assertEqual([], self.errors(document(story(status="IN PROGRESS").replace("Status: IN PROGRESS\n", f"Status: IN PROGRESS\n{line}\n"))))
        self.assertTrue(self.errors(document(story(status="IN PROGRESS").replace("Tasks:\n", f"Tasks:\n{line}\n"))))

    def test_cli_promote_refuses_unexpected_status_line_without_writing(self) -> None:
        original = self.render(document(story(status="DONE", done=True), story("US-1.2", status="BLOCKED", dependency="US-1.1"))).replace("Status: BLOCKED\n", "Status: BLOCKED  \n")
        self.path.write_text(original, encoding="utf-8")
        result = subprocess.run([sys.executable, str(SCRIPT), "promote", "--project-root", str(self.root)], capture_output=True, text=True, check=False)
        self.assertEqual(2, result.returncode)
        self.assertIn("unexpected Status line", result.stderr)
        self.assertEqual(original, self.path.read_text(encoding="utf-8"))

    def test_cli_promote_changes_only_status_and_navigation(self) -> None:
        self.path.write_text(self.render(document(
            story(status="DONE", done=True),
            story("US-1.2", status="BLOCKED", dependency="US-1.1"),
            story("US-1.3", status="BLOCKED", dependency="External: operator decision"),
        )), encoding="utf-8")
        before = self.path.read_text(encoding="utf-8")
        result = subprocess.run([sys.executable, str(SCRIPT), "promote", "--project-root", str(self.root)], capture_output=True, text=True, check=False)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("US-1.2", result.stdout)
        self.assertNotIn("US-1.3", result.stdout)
        after = self.path.read_text(encoding="utf-8")
        context = before.index("## Product Context")
        self.assertEqual(before[context:].replace("Status: BLOCKED", "Status: READY", 1), after[after.index("## Product Context"):])
        self.assertEqual([], self.errors(after, navigation=True))
        again = subprocess.run([sys.executable, str(SCRIPT), "promote", "--project-root", str(self.root)], capture_output=True, text=True, check=False)
        self.assertEqual(0, again.returncode, again.stderr)
        self.assertIn("no story eligible", again.stdout)
        self.assertEqual(after, self.path.read_text(encoding="utf-8"))

    def test_cli_promote_preserves_crlf(self) -> None:
        original = self.render(document(story(status="DONE", done=True), story("US-1.2", status="BLOCKED", dependency="US-1.1"))).replace("\n", "\r\n")
        self.path.write_bytes(original.encode("utf-8"))
        result = subprocess.run([sys.executable, str(SCRIPT), "promote", "--project-root", str(self.root)], capture_output=True, text=True, check=False)
        self.assertEqual(0, result.returncode, result.stderr)
        after = self.path.read_bytes().decode("utf-8")
        self.assertIn("Status: READY\r\n", after)
        self.assertNotIn("\n", after.replace("\r\n", ""))

    def test_cli_rejects_path_outside_root(self) -> None:
        result = subprocess.run([sys.executable, str(SCRIPT), "validate", "--project-root", str(self.root), "--path", str(SCRIPT)], capture_output=True, text=True, check=False)
        self.assertEqual(2, result.returncode)
        self.assertIn("within the project root", result.stderr)


if __name__ == "__main__":
    unittest.main()
