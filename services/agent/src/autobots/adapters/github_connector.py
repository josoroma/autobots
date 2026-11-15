"""The one configured GitHub repository, its token and its HTTP, for every GitHub tool: Decision
0007, widened by Decision 0022 D6, and Decision 0025.

The repository is server configuration, so a model can't choose it, and the token is read for each
attempt and kept nowhere (PK-01). An attempt resolves both once and opens one client, so one call
can't read two repositories (refactor plan R-62, PADP-06). A read's failure is a typed code, and a
write's is a failure only when GitHub's status proves nothing was written (PADP-04).
"""

import base64
import binascii
import re
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, Field, RootModel

from autobots.adapters.provider_http import (
    MALFORMED,
    ProviderReply,
    Text,
    UnclearReply,
    http_client,
    parsed,
    write,
    write_json,
)
from autobots.application.approvals import ApprovedRequest
from autobots.application.tool_gateway import ToolContext, ToolFailed
from autobots.domain.tool_catalog import KeyRequirement

API_URL = "https://api.github.com"
REPOSITORY_VARIABLE = "GITHUB_REPOSITORY"
TOKEN_VARIABLE = "GITHUB_TOKEN"
# Decision 0022 D6: a fine-grained token limited to the one repository, with exactly these.
TOKEN_SCOPES = (
    "Issues: read and write",
    "Pull requests: read and write",
    "Contents: read and write",
    "Actions: read",
    "Metadata: read",
)
GITHUB_KEY = KeyRequirement("github", (REPOSITORY_VARIABLE, TOKEN_VARIABLE), TOKEN_SCOPES)
TARGET_PREFIX = "GitHub repository "
# Each request's bound. Every GitHub tool's timeout is longer: 30 s for the reads and the issue, and
# 60 s for a pull request (tests/test_github_connector.py).
REQUEST_SECONDS = 15.0
PROVIDER = "github"
_REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
_HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}

# A read GitHub refused for a reason of the request, the token or the repository, such as a 409 for
# an empty repository's refs. Any other status, a 5xx among them, is `github_unavailable`.
READ_REFUSED = frozenset({400, 401, 403, 404, 409, 410, 422, 429})
# Statuses GitHub returns to an issue create before it creates anything: a malformed request (400),
# a token it rejects or that lacks the scope (401, 403, which includes its secondary rate limit), a
# repository it can't see (404), issues turned off (410), a validation failure (422) and a rate
# limit (429). It doesn't document 409 here. Any other reply stays unknown and is settled by reading
# the repository's issues back.
ISSUE_WRITE_REFUSED = frozenset({400, 401, 403, 404, 410, 422, 429})
# Tree, commit and ref creates add 409, a conflict GitHub refuses before writing, such as an empty
# repository or a ref already in the way.
GIT_WRITE_REFUSED = frozenset({400, 401, 403, 404, 409, 410, 422, 429})
# A pull request create leaves out 422: GitHub also answers it when a pull request from the branch
# already exists, as after a lost reply the open list didn't show yet. That stays unknown until the
# branch's open pull request is read back (github_pulls.open_pull_request).
PULL_WRITE_REFUSED = frozenset({400, 401, 403, 404, 409, 410, 429})


def github_read_code(status: int) -> str:
    """One mapping for every GitHub read (PADP-04)."""
    return f"github_refused_{status}" if status in READ_REFUSED else "github_unavailable"


def marker(operation_id: str | None) -> str:
    """Written into what a write creates, so a readback finds it by its operation."""
    return f"<!-- autobots-operation:{operation_id} -->"


class Sha(ProviderReply):
    sha: str


class RefReply(ProviderReply):
    target: Sha = Field(alias="object")


class FileReply(ProviderReply):
    type: Text = ""
    content: Text = ""
    sha: Text = ""
    size: int | None = None


class ContentReply(RootModel[FileReply | list[object]]):
    """A path's content: one entry for a file, a list for a directory."""

    def file(self) -> FileReply:
        if not isinstance(self.root, FileReply) or self.root.type != "file":
            raise ToolFailed("github_path_not_a_file")
        return self.root


def file_text(entry: FileReply) -> tuple[bytes, str]:
    """A file's bytes and its text, or `github_file_not_text`. GitHub's base64 is ASCII, so content
    that isn't is no reply of the shape it sends: `provider_reply_malformed`."""
    try:
        raw = base64.b64decode(entry.content, validate=False)
        return raw, raw.decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        raise ToolFailed("github_file_not_text") from None
    except ValueError:
        raise ToolFailed(MALFORMED) from None


async def _configured(
    context: ToolContext, environ: Mapping[str, str]
) -> tuple[str | None, str | None]:
    """The repository and token resolved for the run's workspace by Decision 0025's order."""
    from autobots.application.tool_keys import ToolKeyUnavailable, github_target

    try:
        return await github_target(context.connection, context.scope.workspace_id, environ)
    except ToolKeyUnavailable as error:
        raise ToolFailed(error.code) from None


def approved_repository(approved: ApprovedRequest | None) -> str | None:
    """The repository an approval recorded, or None without one (Decision 0025 V7)."""
    target = (approved.resource_target if approved is not None else None) or ""
    return target.removeprefix(TARGET_PREFIX) if target.startswith(TARGET_PREFIX) else None


async def attempt_credentials(context: ToolContext, environ: Mapping[str, str]) -> tuple[str, str]:
    """This attempt's repository and token.

    A write that already has an approval uses the repository that approval recorded (V7), so
    neither a fresh attempt nor a readback can be pointed at another repository by a changed
    setting. The gateway refuses a fresh approved call whose repository now resolves differently,
    and hands an approved attempt what was approved (XMOD-02).
    """
    repository, token = await _configured(context, environ)
    approved = approved_repository(context.approval)
    if approved is not None:
        repository = approved
    if not token or not repository or not _REPOSITORY.fullmatch(repository):
        raise ToolFailed("connector_not_configured")
    return repository, token


async def approval_label(context: ToolContext, environ: Mapping[str, str]) -> str:
    """What a GitHub write's approval records: the repository resolved for this workspace now."""
    repository, token = await _configured(context, environ)
    if not token or not repository:
        raise ToolFailed("connector_not_configured")
    return f"{TARGET_PREFIX}{repository}"


@dataclass(frozen=True)
class GithubApi:
    """One attempt's repository and client."""

    repository: str
    client: httpx.AsyncClient

    def repo(self, path: str) -> str:
        """`path` inside the configured repository."""
        return f"/repos/{self.repository}{path}"

    async def get(self, path: str, params: Mapping[str, str | int] | None = None) -> httpx.Response:
        """GitHub's answer to a read, whatever its status. Nothing is written by a read, so a
        transport error is a failure."""
        try:
            return await self.client.get(path, params=params)
        except httpx.HTTPError:
            raise ToolFailed("destination_unreachable") from None

    async def read[T: BaseModel](
        self, path: str, model: type[T], params: Mapping[str, str | int] | None = None
    ) -> T:
        reply = await self.get(path, params)
        if reply.status_code != 200:
            raise ToolFailed(github_read_code(reply.status_code))
        return parsed(reply, model)

    async def find[T: BaseModel](
        self, path: str, model: type[T], params: Mapping[str, str | int] | None = None
    ) -> T | None:
        """As `read`, and None where GitHub has nothing at the path."""
        reply = await self.get(path, params)
        if reply.status_code == 404:
            return None
        if reply.status_code != 200:
            raise ToolFailed(github_read_code(reply.status_code))
        return parsed(reply, model)

    async def settle[T: BaseModel](
        self, path: str, model: type[T], params: Mapping[str, str | int] | None = None
    ) -> T:
        """A read that decides whether a write happened. One GitHub answered unclearly, with a body
        that can't be read, or not at all says nothing about it, so the outcome stays unknown."""
        try:
            reply = await self.client.get(path, params=params)
        except httpx.HTTPError:
            raise UnclearReply(PROVIDER, None) from None
        if reply.status_code != 200:
            raise UnclearReply(PROVIDER, reply.status_code)
        try:
            return model.model_validate_json(reply.content)
        except ValueError:
            raise UnclearReply(PROVIDER, reply.status_code) from None

    async def create[T: BaseModel](
        self, path: str, payload: Mapping[str, object], model: type[T], refused: frozenset[int]
    ) -> T:
        return await write_json(
            self.client, path, payload, model, provider=PROVIDER, refused=refused
        )

    async def create_only(
        self, path: str, payload: Mapping[str, object], refused: frozenset[int]
    ) -> None:
        """A create whose reply the tool doesn't use. A 201 is all it needs."""
        await write(self.client, path, payload, provider=PROVIDER, refused=refused)


@dataclass(frozen=True)
class GithubConnector:
    """What every GitHub tool closes over: its transport, which tests replace, and the environment
    its repository and token are read from on each attempt."""

    transport: httpx.AsyncBaseTransport | None
    environ: Mapping[str, str]

    @asynccontextmanager
    async def attempt(self, context: ToolContext) -> AsyncIterator[GithubApi]:
        """The repository and token resolved once, and one client for this attempt."""
        repository, token = await attempt_credentials(context, self.environ)
        async with http_client(
            API_URL,
            timeout=REQUEST_SECONDS,
            headers={**_HEADERS, "Authorization": f"Bearer {token}"},
            transport=self.transport,
        ) as client:
            yield GithubApi(repository, client)

    async def approval_label(self, _arguments: object, context: ToolContext) -> str:
        """The approval's target, as `ApprovalPolicy.target_resolver` asks for it."""
        return await approval_label(context, self.environ)
