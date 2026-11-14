#!/usr/bin/env python3
"""Validate and render the local adaptation of OhMyOrch's SPECS grammar.

Python 3.12+, standard library only. Validation is read-only. Rendering owns only
the three navigation sections preceding Product Context, never story content.
This checks structure and references, not whether a requirement is justified or
whether an implementation/evidence claim is true.
"""

from __future__ import annotations

import argparse
import html
import os
import re
import stat
import sys
import tempfile
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlsplit

STATUSES = {"READY", "NEEDS CLARIFICATION", "BLOCKED", "IN PROGRESS", "DONE"}
NAVIGATION = ("Table of Contents", "Work Item Status", "Dependency Diagram")
FIELDS = (
    "Status", "Source", "Codebase Context", "Acceptance Criteria",
    "Dependencies", "Tasks", "Open Questions",
)
REQUIRED_FIELDS = set(FIELDS) - {"Codebase Context"}
EPIC = re.compile(r"# (EPIC-([1-9]\d*)): (\S.*)")
STORY = re.compile(r"### (US-([1-9]\d*)\.([1-9]\d*)): (\S.*)")
FIELD = re.compile(r"(" + "|".join(re.escape(name) for name in FIELDS) + r"):\s*(.*)")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
LINK = re.compile(r"\[([^\]\n]+)\]\((<[^>\n]+>|[^\s)]+)\)")
SECTION_ID = re.compile(r"\b[A-Z][A-Z0-9]*-[A-Z]*\d+(?:\.\d+)*\b|(?:§|[Ss]ection[s]?)\s*\d+(?:\.\d+)*")


@dataclass(frozen=True)
class Issue:
    line: int
    message: str

    def __str__(self) -> str:
        return f"line {self.line}: {self.message}"


@dataclass
class Task:
    title: str
    done: bool


@dataclass
class Story:
    id: str
    title: str
    epic_id: str
    line: int
    body: list[tuple[int, str]] = field(default_factory=list)
    status: str = ""
    status_line: int = 0
    dependencies: list[str] = field(default_factory=list)
    external_dependencies: list[str] = field(default_factory=list)
    unresolved_questions: list[str] = field(default_factory=list)
    qualified_dependency: bool = False
    tasks: list[Task] = field(default_factory=list)


@dataclass
class Epic:
    id: str
    title: str
    line: int
    stories: list[Story] = field(default_factory=list)


@dataclass
class Document:
    epics: list[Epic]
    issues: list[Issue]

    @property
    def stories(self) -> list[Story]:
        return [story for epic in self.epics for story in epic.stories]


def anchor(text: str) -> str:
    """Upstream anchor rule: lowercase, discard punctuation, hyphenate spaces."""
    text = "".join(
        char for char in text.lower()
        if char.isspace() or char in "_-" or unicodedata.category(char)[0] in "LN"
    )
    return re.sub(r"\s", "-", text)


def outside_fences(lines: list[str]) -> list[bool]:
    """Recognize Markdown fences including outer four-backtick examples."""
    result: list[bool] = []
    opening: str | None = None
    for line in lines:
        match = FENCE.match(line)
        if opening is not None:
            result.append(False)
            if match and match[1][0] == opening[0] and len(match[1]) >= len(opening) and not match[2].strip():
                opening = None
        elif match:
            result.append(False)
            opening = match[1]
        else:
            result.append(True)
    return result


def fenced_blocks(entries: list[tuple[int, str]]) -> tuple[list[tuple[int, str, list[str]]], bool]:
    blocks: list[tuple[int, str, list[str]]] = []
    opening: str | None = None
    language = ""
    start = 0
    content: list[str] = []
    for number, line in entries:
        match = FENCE.match(line)
        if opening is None and match:
            opening, language, start, content = match[1], match[2].strip(), number, []
        elif opening is not None:
            if match and match[1][0] == opening[0] and len(match[1]) >= len(opening) and not match[2].strip():
                blocks.append((start, language, content))
                opening = None
            else:
                content.append(line)
    return blocks, opening is not None


def list_items(entries: list[tuple[int, str]], issues: list[Issue], label: str) -> list[tuple[int, str]]:
    items: list[tuple[int, str]] = []
    for number, text in entries:
        if not text.strip():
            continue
        match = re.fullmatch(r"- (\S.*)", text)
        if match:
            items.append((number, match[1]))
        else:
            issues.append(Issue(number, f"{label} requires '- ' list items"))
    return items


def is_none(text: str) -> bool:
    return text in {"None", "None."}


def local_source(target: str, base: Path, root: Path) -> tuple[Path, str]:
    parsed = urlsplit(target.removeprefix("<").removesuffix(">"))
    if parsed.scheme or parsed.netloc or parsed.query:
        raise ValueError("source must be a local file link without a query")
    raw_path = unquote(parsed.path)
    if not raw_path or raw_path.startswith("/") or "\\" in raw_path or "\x00" in raw_path:
        raise ValueError("source must use a relative local file path")
    resolved = (base / raw_path).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("source escapes project root")
    if not resolved.is_file():
        raise ValueError("source file does not exist")
    if resolved.suffix.lower() not in {".md", ".markdown"}:
        raise ValueError("source must be a Markdown document, not a secret/configuration or code file")
    return resolved, unquote(parsed.fragment)


def source_locations(text: str) -> tuple[set[str], list[str]]:
    """ATX/Setext headings and explicit HTML IDs, ignoring fenced examples."""
    lines = text.splitlines()
    visible = outside_fences(lines)
    headings: list[str] = []
    identifiers: set[str] = set()
    heading_ids: set[str] = set()
    for index, (line, outside) in enumerate(zip(lines, visible, strict=True)):
        if not outside:
            continue
        heading = re.fullmatch(r" {0,3}#{1,6}\s+(.+?)(?:\s+#+)?\s*", line)
        heading_title: str | None = None
        if heading:
            heading_title = heading[1]
        elif index and visible[index - 1] and lines[index - 1].strip() and re.fullmatch(r" {0,3}(?:={3,}|-{3,})\s*", line):
            heading_title = lines[index - 1].strip()
        for explicit in re.finditer(r"<[^>]+\bid\s*=\s*(['\"])(.*?)\1[^>]*>", line):
            identifiers.add(html.unescape(explicit[2]))
        if heading_title is not None:
            headings.append(heading_title)
            base = anchor(heading_title)
            candidate, suffix = base, 0
            while candidate in heading_ids:
                suffix += 1
                candidate = f"{base}-{suffix}"
            heading_ids.add(candidate)
    return identifiers | heading_ids, headings


def reference_exists(reference: str, text: str, headings: list[str]) -> bool:
    if reference.startswith("§") or reference.lower().startswith("section"):
        number = re.search(r"\d+(?:\.\d+)*", reference)
        return number is not None and any(re.match(re.escape(number[0]) + r"(?:[.\s:]|$)", heading) for heading in headings)
    return re.search(r"(?<![A-Za-z0-9_-])" + re.escape(reference) + r"(?![A-Za-z0-9_-])", text) is not None


def validate_sources(entries: list[tuple[int, str]], base: Path, root: Path, issues: list[Issue]) -> None:
    items = list_items(entries, issues, "Source")
    if not items:
        issues.append(Issue(entries[0][0] if entries else 1, "Source requires at least one local reference"))
    for number, text in items:
        links = list(LINK.finditer(text))
        if not links:
            issues.append(Issue(number, "Source requires a Markdown file link and section/requirement reference"))
        for index, link in enumerate(links):
            try:
                path, fragment = local_source(link[2], base, root)
                source_text = path.read_bytes().decode("utf-8")
                locations, headings = source_locations(source_text)
                end = links[index + 1].start() if index + 1 < len(links) else len(text)
                references = list(SECTION_ID.finditer(link[1] + " " + text[link.end():end]))
                if fragment and fragment not in locations:
                    issues.append(Issue(number, f"source heading/HTML id '#{fragment}' does not exist in {path.name}"))
                if not fragment and not references:
                    issues.append(Issue(number, "Source needs a heading fragment or explicit section/requirement ID"))
                if not fragment:
                    for reference in references:
                        if not reference_exists(reference[0], source_text, headings):
                            issues.append(Issue(number, f"source section/requirement '{reference[0]}' does not exist in {path.name}"))
            except (OSError, UnicodeError, ValueError) as error:
                issues.append(Issue(number, str(error)))


def validate_gherkin(entries: list[tuple[int, str]], issues: list[Issue], story_line: int) -> None:
    blocks, unclosed = fenced_blocks(entries)
    for (number, text), visible in zip(entries, outside_fences([text for _, text in entries]), strict=True):
        if visible and text.strip():
            issues.append(Issue(number, "Acceptance Criteria must contain only fenced Gherkin scenarios"))
    if unclosed:
        issues.append(Issue(story_line, "unclosed acceptance code fence"))
    scenarios = 0
    for number, language, content in blocks:
        if language != "gherkin":
            issues.append(Issue(number, "acceptance blocks must be labelled gherkin"))
            continue
        current: tuple[int, str] | None = None
        seen: list[str] = []

        def finish() -> None:
            if current is not None and seen != ["Given", "When", "Then"]:  # noqa: B023 - called within this iteration, so it reads this iteration's values
                issues.append(Issue(current[0], f"Scenario '{current[1]}' requires ordered Given, When, Then"))  # noqa: B023 - called within this iteration, so it reads this iteration's values

        for offset, line in enumerate(content, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            scenario = re.fullmatch(r"Scenario: (\S.*)", stripped)
            if scenario:
                finish()
                current, seen = (number + offset, scenario[1]), []
                scenarios += 1
                continue
            step = re.fullmatch(r"(Given|When|Then|And|But) (\S.*)", stripped)
            if current is None or step is None:
                issues.append(Issue(number + offset, "expected Scenario or a Given/When/Then/And/But step"))
            elif step[1] in {"Given", "When", "Then"}:
                if not seen or seen[-1] != step[1]:
                    seen.append(step[1])
            elif not seen:
                issues.append(Issue(number + offset, "And/But must follow a primary step"))
        finish()
    if not scenarios:
        issues.append(Issue(story_line, "Acceptance Criteria requires at least one Gherkin Scenario"))


def validate_story(story: Story, base: Path, root: Path, issues: list[Issue]) -> None:
    sections: dict[str, list[tuple[int, str]]] = {}
    section: str | None = None
    previous_field = -1
    outside = outside_fences([text for _, text in story.body])
    for (number, text), visible in zip(story.body, outside, strict=True):
        match = FIELD.fullmatch(text) if visible else None
        if match:
            section = match[1]
            position = FIELDS.index(section)
            if position < previous_field:
                issues.append(Issue(number, f"{section} is out of the required story field order"))
            previous_field = position
            if section in sections:
                issues.append(Issue(number, f"duplicate {section} field in {story.id}"))
            else:
                sections[section] = []
            if match[2]:
                sections[section].append((number, match[2]))
        elif section is not None:
            sections[section].append((number, text))
    for missing in sorted(REQUIRED_FIELDS - sections.keys()):
        issues.append(Issue(story.line, f"{story.id} missing {missing} field"))

    status_lines = [(n, text) for n, text in sections.get("Status", []) if text.strip()]
    # The user-story prose follows Status, before Source, in the upstream shape.
    if status_lines:
        story.status_line, story.status = status_lines[0][0], status_lines[0][1].strip()
    if story.status not in STATUSES:
        issues.append(Issue(story.line, f"{story.id} has invalid or missing Status"))
    prose = "\n".join(text for _, text in status_lines[1:])
    if not all(re.search(r"(?m)^" + prefix + r"\s+\S", prose) for prefix in ("As an?", "I want", "So that")):
        issues.append(Issue(story.line, f"{story.id} requires As a / I want / So that story prose"))

    validate_sources(sections.get("Source", []), base, root, issues)
    if "Codebase Context" in sections:
        validate_sources(sections["Codebase Context"], base, root, issues)
    validate_gherkin(sections.get("Acceptance Criteria", []), issues, story.line)
    dependencies = list_items(sections.get("Dependencies", []), issues, "Dependencies")
    if not dependencies:
        issues.append(Issue(story.line, f"{story.id} requires Dependencies or '- None'"))
    for number, text in dependencies:
        if is_none(text):
            if len(dependencies) != 1:
                issues.append(Issue(number, "None cannot be combined with dependencies"))
            continue
        match = re.fullmatch(r"(US-[1-9]\d*\.[1-9]\d*)(?:\s.*|\.)?", text)
        if match:
            if match[1] in story.dependencies:
                issues.append(Issue(number, f"duplicate dependency {match[1]}"))
            story.dependencies.append(match[1])
            story.qualified_dependency |= text not in {match[1], match[1] + "."}
        elif re.fullmatch(r"External: \S.*", text):
            story.external_dependencies.append(text.removeprefix("External: "))
        else:
            issues.append(Issue(number, "dependency must be US-N.M, External: explanation, or None"))

    for number, text in list_items(sections.get("Tasks", []), issues, "Tasks"):
        match = re.fullmatch(r"\[([ xX])\] (\S.*)", text)
        if not match:
            issues.append(Issue(number, "task requires an unchecked or checked Markdown checkbox"))
        else:
            story.tasks.append(Task(match[2], match[1].lower() == "x"))
    if not story.tasks:
        issues.append(Issue(story.line, f"{story.id} requires at least one task"))
    if story.status == "DONE" and any(not task.done for task in story.tasks):
        issues.append(Issue(story.line, f"{story.id} is DONE with unfinished tasks"))

    questions = list_items(sections.get("Open Questions", []), issues, "Open Questions")
    unresolved = [text for _, text in questions if not is_none(text)]
    story.unresolved_questions = unresolved
    if not questions:
        issues.append(Issue(story.line, f"{story.id} requires Open Questions or '- None'"))
    if unresolved and any(is_none(text) for _, text in questions):
        issues.append(Issue(story.line, "None cannot be combined with unresolved Open Questions"))
    if unresolved and story.status not in {"BLOCKED", "NEEDS CLARIFICATION"}:
        issues.append(Issue(story.line, f"{story.id} has unresolved Open Questions but is {story.status}"))
    if story.status == "NEEDS CLARIFICATION" and not unresolved:
        issues.append(Issue(story.line, f"{story.id} NEEDS CLARIFICATION requires an Open Question"))
    if any(re.search(r"\bconflict(?:s|ing)?\b", question, re.IGNORECASE) for question in unresolved) and story.status != "BLOCKED":
        issues.append(Issue(story.line, f"{story.id} source conflict requires BLOCKED status"))


def parse_document(text: str, root: Path, path: Path) -> Document:
    lines = text.splitlines()
    visible = outside_fences(lines)
    issues: list[Issue] = []
    epics: list[Epic] = []
    epic: Epic | None = None
    story: Story | None = None
    ids: set[str] = set()
    if fenced_blocks(list(enumerate(lines, start=1)))[1]:
        issues.append(Issue(1, "document contains an unclosed code fence"))
    for number, (line, outside) in enumerate(zip(lines, visible, strict=True), start=1):
        epic_match = EPIC.fullmatch(line) if outside else None
        story_match = STORY.fullmatch(line) if outside else None
        if epic_match:
            epic = Epic(epic_match[1], epic_match[3], number)
            epics.append(epic)
            story = None
            identifier = epic.id
        elif story_match:
            identifier = story_match[1]
            if epic is None:
                issues.append(Issue(number, f"{identifier} has no enclosing epic"))
                continue
            if story_match[2] != epic.id.removeprefix("EPIC-"):
                issues.append(Issue(number, f"{identifier} does not belong to {epic.id}"))
            story = Story(identifier, story_match[4], epic.id, number)
            epic.stories.append(story)
        else:
            if outside and re.match(r"^#{1,6}\s+(?:EPIC|US)(?:\b|[-_])", line, re.IGNORECASE):
                issues.append(Issue(number, "malformed epic/story heading or ID"))
            if story is not None:
                story.body.append((number, line))
            continue
        if identifier in ids:
            issues.append(Issue(number, f"duplicate ID {identifier}"))
        ids.add(identifier)
    document = Document(epics, issues)
    if not epics:
        issues.append(Issue(1, "no EPIC-N headings found"))
    for epic in epics:
        if not epic.stories:
            issues.append(Issue(epic.line, f"{epic.id} has no stories"))
    for item in document.stories:
        validate_story(item, path.parent, root, issues)
    by_id = {item.id: item for item in document.stories}
    for item in document.stories:
        for dependency in item.dependencies:
            if dependency not in by_id:
                issues.append(Issue(item.line, f"{item.id} depends on missing {dependency}"))
        if item.status in {"READY", "IN PROGRESS", "DONE"}:
            unfinished = [dep for dep in item.dependencies if dep not in by_id or by_id[dep].status != "DONE"]
            if unfinished or item.external_dependencies:
                issues.append(Issue(item.line, f"{item.id} {item.status} requires all dependencies DONE and no unresolved External dependency"))

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(identifier: str, chain: list[str]) -> None:
        if identifier in visiting:
            issues.append(Issue(by_id[identifier].line, "dependency cycle: " + " -> ".join([*chain, identifier])))
            return
        if identifier in visited:
            return
        visiting.add(identifier)
        for dependency in by_id[identifier].dependencies:
            if dependency in by_id:
                visit(dependency, [*chain, identifier])
        visiting.remove(identifier)
        visited.add(identifier)

    for identifier in by_id:
        visit(identifier, [])
    return document


def node_id(identifier: str) -> str:
    return identifier.replace("-", "_").replace(".", "_").replace("#", "_")


def label(text: str) -> str:
    return html.escape(text, quote=True)


def table_text(text: str) -> str:
    return text.replace("|", r"\|")


def link_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("[", r"\[").replace("]", r"\]")


def render_navigation(document: Document) -> str:
    result = ["## Table of Contents", ""]
    for epic in document.epics:
        title = f"{epic.id}: {epic.title}"
        result.append(f"- [{link_text(title)}](#{anchor(title)})")
        for story in epic.stories:
            title = f"{story.id}: {story.title}"
            result.append(f"  - [{link_text(title)}](#{anchor(title)})")
    result.extend(["", "## Work Item Status", "", "| ID | Title | Status | Parent |", "|---|---|---|---|"])
    for epic in document.epics:
        result.append(f"| {epic.id} | {table_text(epic.title)} | — | — |")
        for story in epic.stories:
            result.append(f"| {story.id} | {table_text(story.title)} | {story.status} | {epic.id} |")
            for index, task in enumerate(story.tasks, start=1):
                result.append(f"| {story.id}#{index} | {table_text(task.title)} | {'DONE' if task.done else 'TODO'} | {story.id} |")
    result.extend(["", "## Dependency Diagram", "", "```mermaid", "flowchart TD"])
    for epic in document.epics:
        result.append(f'  subgraph {node_id(epic.id)}["{label(epic.id + ": " + epic.title)}"]')
        for story in epic.stories:
            result.append(f'    {node_id(story.id)}["{label(story.id + ": " + story.title)}"]')
        result.append("  end")
    for story in document.stories:
        for dependency in story.dependencies:
            result.append(f"  {node_id(dependency)} -.-> {node_id(story.id)}")
        for index, dependency in enumerate(story.external_dependencies, start=1):
            identifier = f"EXT_{node_id(story.id)}_{index}"
            result.append(f'  {identifier}["{label("External: " + dependency)}"]')
            result.append(f"  {identifier} -.-> {node_id(story.id)}")
    result.append("```")
    for epic in document.epics:
        result.extend(["", "```mermaid", "flowchart TD", f'  subgraph {node_id(epic.id)}["{epic.id} tasks"]'])
        for story in epic.stories:
            result.append(f'    {node_id(story.id)}["{label(story.id + ": " + story.title)}"]')
            for index, task in enumerate(story.tasks, start=1):
                identifier = f"T_{node_id(story.id).removeprefix('US_')}_{index}"
                result.append(f'    {identifier}["{label(story.id + "#" + str(index) + ": " + task.title)}"]')
                result.append(f"    {node_id(story.id)} --> {identifier}")
        result.extend(["  end", "```"])
    return "\n".join(result) + "\n\n"


def navigation_bounds(text: str) -> tuple[int, int]:
    lines = text.splitlines(keepends=True)
    plain = [line.rstrip("\r\n") for line in lines]
    visible = outside_fences(plain)
    offsets: list[int] = []
    offset = 0
    for line in lines:
        offsets.append(offset)
        offset += len(line)
    contexts = [i for i, line in enumerate(plain) if visible[i] and line == "## Product Context"]
    if len(contexts) != 1:
        raise ValueError("exactly one '## Product Context' heading is required")
    context = contexts[0]
    navigation = [(i, line.removeprefix("## ")) for i, line in enumerate(plain) if visible[i] and line in {"## " + name for name in NAVIGATION}]
    if not navigation:
        return offsets[context], offsets[context]
    if [name for _, name in navigation] != list(NAVIGATION) or any(i >= context for i, _ in navigation):
        raise ValueError("navigation must contain the three required headings once, in order, before Product Context")
    start = navigation[0][0]
    allowed = {"## " + name for name in NAVIGATION}
    if any(visible[i] and plain[i].startswith("#") and plain[i] not in allowed for i in range(start, context)):
        raise ValueError("refusing to replace non-navigation headings in the generated region")
    return offsets[start], offsets[context]


def render_text(text: str, document: Document) -> str:
    start, end = navigation_bounds(text)
    newline = "\r\n" if "\r\n" in text else "\n"
    return text[:start] + render_navigation(document).replace("\n", newline) + text[end:]


def validate_text(text: str, root: Path, path: Path, *, navigation: bool = True) -> Document:
    document = parse_document(text, root.resolve(), path.resolve())
    try:
        rendered = render_text(text, document)
        if navigation and rendered != text:
            document.issues.append(Issue(1, "navigation is missing or stale; run scripts/specs.py render"))
    except ValueError as error:
        document.issues.append(Issue(1, str(error)))
    return document


def promotable(document: Document) -> list[Story]:
    """BLOCKED stories whose only blocker was declared story dependencies, all now DONE.

    External dependencies and open questions (including source conflicts) are human
    decisions, so those stories stay BLOCKED. A BLOCKED story that declares no story
    dependency is blocked for an unrecorded reason and is also left alone, as is one
    whose dependency line carries prose that could hide another blocker.

    A human hold on a story whose dependencies are all DONE must be recorded as an
    open question or External dependency; a bare BLOCKED status would be promoted.
    """
    status = {story.id: story.status for story in document.stories}
    return [
        story for story in document.stories
        if story.status == "BLOCKED" and story.dependencies and not story.qualified_dependency
        and not story.external_dependencies and not story.unresolved_questions
        and all(status.get(dependency) == "DONE" for dependency in story.dependencies)
    ]


def promote_text(text: str, document: Document) -> tuple[str, list[str]]:
    """Set each promotable story to READY; only its own Status line changes."""
    lines = text.splitlines(keepends=True)  # Same numbering as parse_document.
    promoted = []
    for story in promotable(document):
        line = lines[story.status_line - 1]
        content = line.rstrip("\r\n")
        if content != "Status: BLOCKED":
            raise ValueError(f"{story.id}: refusing to promote an unexpected Status line")
        lines[story.status_line - 1] = "Status: READY" + line[len(content):]
        promoted.append(story.id)
    return "".join(lines), promoted


def write_if_unchanged(path: Path, original: bytes, updated: bytes) -> None:
    """Atomic replacement, preserving mode and refusing an observed concurrent edit."""
    mode = stat.S_IMODE(path.stat().st_mode)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".specs-", delete=False) as stream:
            temporary = stream.name
            stream.write(updated)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        if path.read_bytes() != original:
            raise ValueError("SPECS changed while rendering; retry against the current file")
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            os.unlink(temporary)


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < (3, 12):  # noqa: UP036 - a guard for an older interpreter running this script
        print('ERROR: Python 3.12+ is required; use the qualified python3.12 interpreter.', file=sys.stderr)
        return 2
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "render", "promote"))
    parser.add_argument("--path", default="SPECS.md", help="file relative to project root")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        root = args.project_root.resolve(strict=True)
        path = (root / args.path).resolve(strict=True)
        if not root.is_dir() or not path.is_relative_to(root) or not path.is_file():
            raise ValueError("SPECS path must be a file within the project root")
        original = path.read_bytes()
        text = original.decode("utf-8")
        document = validate_text(text, root, path, navigation=args.command == "validate")
        if document.issues:
            for issue in document.issues:
                print(f"FAIL: {issue}", file=sys.stderr)
            return 1
        if args.command == "promote":
            text, promoted = promote_text(text, document)
            document = validate_text(text, root, path, navigation=False)
            if document.issues:
                for issue in document.issues:
                    print(f"FAIL: {issue}", file=sys.stderr)
                return 1
            updated = render_text(text, document).encode("utf-8")
            if updated != original:
                write_if_unchanged(path, original, updated)
            print(f"PASS: promote: {', '.join(promoted) or 'no story eligible'}")
            return 0
        if args.command == "render":
            updated = render_text(text, document).encode("utf-8")
            if updated != original:
                write_if_unchanged(path, original, updated)
        print(f"PASS: {args.command}: {len(document.epics)} epics, {len(document.stories)} stories, {sum(len(item.tasks) for item in document.stories)} tasks")
        return 0
    except (OSError, UnicodeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
