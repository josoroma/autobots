"""Tool input fields declared once, each with the bounds its tools publish (refactor plan R-61,
PDOM-07).

A tool's published input schema stays byte-identical, so no tool gets a new version for these
(Decision 0029 F13). A rule the schema doesn't state is a validator here, which the gateway applies
before any request; the URL guard checks every URL at the call (adapters/url_guard.py).
tests/test_tool_schema_versions.py pins each tool version's schemas.
"""

import re
from typing import Annotated

from pydantic import AfterValidator, Field

# A path among the run's own files (SP-013). The gateway's grant check decides where it may be.
RunFilePath = Annotated[str, Field(min_length=1, max_length=500)]
# A run file a tool writes, always under outputs/.
OutputPath = Annotated[str, Field(min_length=1, max_length=500, pattern=r"^outputs/")]


def _inside_the_repository(path: str) -> str:
    if path.startswith("/") or ".." in path.split("/"):
        raise ValueError("a path is relative to the repository and can't climb out of it")
    return path


def _outside_git(path: str) -> str:
    if path.startswith(".git/"):
        raise ValueError("a path is relative to the repository and can't climb out of it")
    return path


# A file in the one configured repository (PRD-Studio GH-04), relative and never climbing out.
RepoPath = Annotated[
    str,
    Field(min_length=1, max_length=500, pattern=r"^[A-Za-z0-9._/ -]+$"),
    AfterValidator(_inside_the_repository),
]
# A file a pull request commits (PRD-Studio GH-06): a repository path outside .git/.
CommitPath = Annotated[RepoPath, AfterValidator(_outside_git)]

# A GitHub issue's or pull request's title and body (PRD-Studio GH-05, GH-06).
IssueTitle = Annotated[str, Field(min_length=1, max_length=256)]
IssueBody = Annotated[str, Field(max_length=60_000)]

# A URL a web tool reads. The URL guard requires https and a public address before any request;
# the schema states only the length (Decision 0029 F13).
GuardedUrl = Annotated[str, Field(min_length=1, max_length=2048)]

SYMBOL_PATTERN = r"[A-Z0-9.^=-]{1,20}"


def _symbol(symbol: str) -> str:
    if not re.fullmatch(SYMBOL_PATTERN, symbol):
        raise ValueError("a symbol is 1 to 20 of A-Z, 0-9 and . ^ = -")
    return symbol


# A market symbol, such as AAPL or ^GSPC (Decision 0017 C11).
Symbol = Annotated[str, AfterValidator(_symbol)]

DOMAIN_PATTERN = r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"


def _domain(domain: str) -> str:
    if not re.fullmatch(DOMAIN_PATTERN, domain):
        raise ValueError("allowed_domains must be lowercase domain names")
    return domain


# A lowercase domain name, such as example.com, that a browsing call stays inside (Decision 0020).
DomainName = Annotated[str, AfterValidator(_domain)]
