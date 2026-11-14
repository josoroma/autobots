"""The code search, with light imports, so a child interpreter can run it (R-20, Decision 0017 C7).

Pure Python over the files it's given: no shell, no binary and no host path. Run as a module, it
reads `{"files": ..., "arguments": ...}` on stdin and writes `{"output": ...}` or
`{"error": "invalid_pattern"}` on stdout.
"""

import fnmatch
import json
import re
import sys
from collections.abc import Mapping

from autobots.contracts.code_tools import (
    MATCH_CHARACTERS,
    SearchFilesInput,
    SearchFilesOutput,
    SearchMatch,
)


class InvalidPattern(ValueError):
    """The pattern doesn't compile."""


def cut(text: str, limit: int = MATCH_CHARACTERS) -> str:
    return text if len(text) <= limit else text[:limit]


def search(files: Mapping[str, str], arguments: SearchFilesInput) -> SearchFilesOutput:
    """The whole search, given each file's latest content. Pure, so it is tested without a run."""
    try:
        pattern = re.compile(arguments.pattern)
    except re.error:
        raise InvalidPattern(arguments.pattern) from None
    chosen = sorted(
        path
        for path in files
        if path.startswith(arguments.path)
        and (
            arguments.file_glob is None
            or fnmatch.fnmatchcase(path.rsplit("/", 1)[-1], arguments.file_glob)
            or fnmatch.fnmatchcase(path, arguments.file_glob)
        )
    )
    if arguments.target == "files":
        named = [path for path in chosen if pattern.search(path)]
        page = named[arguments.offset : arguments.offset + arguments.limit]
        return SearchFilesOutput(
            matches=[],
            files=[] if arguments.output_mode == "count" else page,
            total_count=len(named),
            truncated=arguments.offset + arguments.limit < len(named),
        )
    found: list[SearchMatch] = []
    hit_files: list[str] = []
    for path in chosen:
        lines = files[path].splitlines()
        hits = [index for index, line in enumerate(lines) if pattern.search(line)]
        if hits:
            hit_files.append(path)
        for index in hits:
            found.append(
                SearchMatch(
                    path=path,
                    line_number=index + 1,
                    content=cut(lines[index]),
                    before=[cut(line) for line in lines[max(index - arguments.context, 0) : index]],
                    after=[cut(line) for line in lines[index + 1 : index + 1 + arguments.context]],
                )
            )
    total = len(hit_files) if arguments.output_mode == "files_only" else len(found)
    end = arguments.offset + arguments.limit
    if arguments.output_mode == "count":
        return SearchFilesOutput(matches=[], files=[], total_count=len(found), truncated=False)
    if arguments.output_mode == "files_only":
        return SearchFilesOutput(
            matches=[],
            files=hit_files[arguments.offset : end],
            total_count=total,
            truncated=end < total,
        )
    return SearchFilesOutput(
        matches=found[arguments.offset : end],
        files=[],
        total_count=total,
        truncated=end < total,
    )


def main() -> None:
    request = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    arguments = SearchFilesInput.model_validate(request["arguments"])
    try:
        output = search(request["files"], arguments)
    except InvalidPattern:
        answer: dict[str, object] = {"error": "invalid_pattern"}
    else:
        answer = {"output": output.model_dump(mode="json")}
    sys.stdout.buffer.write(json.dumps(answer).encode("utf-8"))


if __name__ == "__main__":
    main()
