"""The pull-request connector over a fake Git API, PRD-Studio GH-06 and Decision 0022 D6 and D15.

Each write step's refused and unclear replies decide whether the call failed or stays unknown, and
the readback decides whether trying again is safe (refactor plan R-62, PADP-18). The gateway around
it is exercised in tests/db/pull_request_check.py.
"""

import asyncio
import base64
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from urllib.parse import parse_qs, unquote
from uuid import UUID, uuid4

import httpx
import pytest

from autobots.adapters.github_connector import marker
from autobots.adapters.github_pulls import TOOL_ID, branch_for, github_pull_request_tool
from autobots.adapters.provider_http import UnclearReply
from autobots.application.approvals import ApprovedRequest
from autobots.application.tool_definitions import (
    NotDelivered,
    ToolContext,
    ToolDefinition,
    ToolFailed,
    ToolScope,
)
from autobots.contracts.github_tools import GithubOpenPullRequestInput, GithubOpenPullRequestOutput

REPOSITORY = "owner/configured"
ENV = {"GITHUB_REPOSITORY": REPOSITORY, "GITHUB_TOKEN": "github_pat_fixture0001"}
OPERATION = "op-7"
BRANCH = branch_for(OPERATION)
SCOPE = ToolScope(uuid4(), uuid4(), 1, {TOOL_ID: 1})
PROPOSAL = GithubOpenPullRequestInput.model_validate(
    {
        "title": "Fix the docs",
        "body": "Why it changes.",
        "base": "main",
        "files": [
            {"path": "README.md", "content": "Hello\n"},
            {"path": "docs/new.md", "content": "New\n"},
        ],
    }
)
WRITES = ("tree", "commit", "ref", "pull")
Answer = Callable[[], httpx.Response]


def encoded(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


class FakeGit:
    """GitHub's Git data and pulls API for one repository. A step can be answered or raised
    instead, by its name: base_head, branch_head, content, base_commit, the four writes, pulls."""

    def __init__(self) -> None:
        self.heads = {"main": "base-1"}
        self.contents: dict[str, object] = {
            "README.md": {"type": "file", "content": encoded("Hi\n")},
            "docs": {"type": "dir"},
        }
        self.pulls: list[dict[str, object]] = []
        self.requests: list[httpx.Request] = []
        self.answers: dict[str, httpx.Response] = {}
        self.raises: dict[str, Exception] = {}

    def writes(self) -> list[str]:
        return [self._step(request)[0] for request in self.requests if request.method == "POST"]

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        step, answer = self._step(request)
        if step in self.raises:
            raise self.raises[step]
        if step in self.answers:
            return self.answers[step]
        return answer()

    def _step(self, request: httpx.Request) -> tuple[str, Answer]:
        path = unquote(request.url.path).removeprefix(f"/repos/{REPOSITORY}")
        if request.method == "GET":
            return self._read(request, path)
        sent = json.loads(request.content or b"{}")
        writes: dict[str, tuple[str, Answer]] = {
            "/git/trees": ("tree", lambda: created({"sha": "tree-2"})),
            "/git/commits": ("commit", lambda: created({"sha": "commit-2"})),
            "/git/refs": ("ref", lambda: self._ref(sent)),
            "/pulls": ("pull", lambda: self._pull(sent)),
        }
        return writes.get(path, ("unknown", lambda: httpx.Response(599)))

    def _read(self, request: httpx.Request, path: str) -> tuple[str, Answer]:
        if path.startswith("/git/ref/heads/"):
            branch = path.removeprefix("/git/ref/heads/")
            return ("base_head" if branch == "main" else "branch_head"), lambda: self._head(branch)
        if path.startswith("/contents/"):
            found = self.contents.get(path.removeprefix("/contents/"))
            return "content", lambda: httpx.Response(404) if found is None else ok(found)
        if path.startswith("/git/commits/"):
            return "base_commit", lambda: ok({"tree": {"sha": "tree-1"}})
        if path == "/pulls":
            return "pulls", lambda: ok(self._open(request))
        return "unknown", lambda: httpx.Response(599)

    def _head(self, branch: str) -> httpx.Response:
        sha = self.heads.get(branch)
        return httpx.Response(404) if sha is None else ok({"object": {"sha": sha}})

    def _open(self, request: httpx.Request) -> list[dict[str, object]]:
        head = parse_qs(request.url.query.decode())["head"][0]
        return [pull for pull in self.pulls if f"owner:{pull_head(pull)}" == head]

    def _ref(self, sent: dict[str, str]) -> httpx.Response:
        self.heads[sent["ref"].removeprefix("refs/heads/")] = sent["sha"]
        return created({"ref": sent["ref"], "object": {"sha": sent["sha"]}})

    def _pull(self, sent: dict[str, str]) -> httpx.Response:
        number = len(self.pulls) + 1
        pull: dict[str, object] = {
            "number": number,
            "html_url": f"https://github.com/{REPOSITORY}/pull/{number}",
            "head": {"ref": sent["head"], "sha": self.heads.get(sent["head"], "")},
            "body": sent["body"],
        }
        self.pulls.append(pull)
        return created(pull)


def ok(body: object) -> httpx.Response:
    return httpx.Response(200, json=body)


def created(body: object) -> httpx.Response:
    return httpx.Response(201, json=body)


def pull_head(pull: dict[str, object]) -> str:
    head = pull["head"]
    assert isinstance(head, dict)
    return str(head["ref"])


@dataclass(frozen=True)
class Reviewing(ToolContext):
    """A context that records a request sent back to review instead of writing it."""

    returned: list[tuple[str, dict[str, object]]] = field(default_factory=list)

    async def return_to_review(self, tool_id: str, detail: dict[str, object]) -> UUID | None:
        self.returned.append((tool_id, detail))
        return None


def approved(base_sha: str = "base-1") -> Reviewing:
    detail: dict[str, object] = {"base_branch": "main", "base_sha": base_sha, "files": []}
    approval = ApprovedRequest(f"GitHub repository {REPOSITORY}", detail)
    return Reviewing(None, SCOPE, OPERATION, approval)


def settled[T](awaitable: Awaitable[T]) -> T:
    """Runs a tool's handler, readback or resolver, which are typed as plain awaitables."""

    async def wait() -> T:
        return await awaitable

    return asyncio.run(wait())


def tool(git: FakeGit) -> ToolDefinition:
    return github_pull_request_tool(httpx.MockTransport(git), ENV)


def open_pull(git: FakeGit, context: Reviewing | None = None) -> GithubOpenPullRequestOutput:
    output = settled(tool(git).handler(PROPOSAL, context or approved()))
    assert isinstance(output, GithubOpenPullRequestOutput)
    return output


def read_back(git: FakeGit) -> GithubOpenPullRequestOutput | None:
    reconcile = tool(git).reconcile
    assert reconcile is not None
    found = settled(reconcile(PROPOSAL, approved()))
    assert found is None or isinstance(found, GithubOpenPullRequestOutput)
    return found


def review(git: FakeGit) -> dict[str, object]:
    detail = tool(git).approval.review_detail
    assert detail is not None
    return settled(detail(PROPOSAL, approved()))


def test_an_approved_request_opens_one_pull_request_from_its_own_branch() -> None:
    git = FakeGit()
    output = open_pull(git)
    assert git.writes() == list(WRITES)
    assert output == GithubOpenPullRequestOutput(
        number=1,
        url=f"https://github.com/{REPOSITORY}/pull/1",
        branch=BRANCH,
        head_sha="commit-2",
    )
    posted = {
        git._step(request)[0]: json.loads(request.content)
        for request in git.requests
        if request.method == "POST"
    }
    assert posted["tree"]["base_tree"] == "tree-1"
    assert [item["path"] for item in posted["tree"]["tree"]] == ["README.md", "docs/new.md"]
    assert posted["commit"] == {"message": "Fix the docs", "tree": "tree-2", "parents": ["base-1"]}
    assert posted["ref"] == {"ref": f"refs/heads/{BRANCH}", "sha": "commit-2"}
    assert posted["pull"]["head"] == BRANCH and posted["pull"]["base"] == "main"
    assert marker(OPERATION) in posted["pull"]["body"]
    for request in git.requests:
        assert request.url.host == "api.github.com"
        assert request.headers["authorization"] == "Bearer github_pat_fixture0001"


@pytest.mark.parametrize(
    ("step", "status"),
    [
        (step, status)
        for step in WRITES
        for status in (400, 401, 403, 404, 409, 410, 422, 429)
        if (step, status) != ("pull", 422)
    ],
)
def test_a_refused_write_fails_and_writes_nothing_after_it(step: str, status: int) -> None:
    git = FakeGit()
    git.answers[step] = httpx.Response(status, json={"message": "arranged"})
    with pytest.raises(ToolFailed, match=rf"^github_refused_{status}$"):
        open_pull(git)
    assert git.writes() == list(WRITES[: WRITES.index(step) + 1])


@pytest.mark.parametrize("step", WRITES)
@pytest.mark.parametrize("status", [200, 202, 302, 500, 502, 503])
def test_an_unclear_write_stays_unknown(step: str, status: int) -> None:
    git = FakeGit()
    git.answers[step] = httpx.Response(status, json={"message": "arranged"})
    with pytest.raises(UnclearReply) as unclear:
        open_pull(git)
    assert unclear.value.detail == f"github_unclear_{status}"
    assert git.writes() == list(WRITES[: WRITES.index(step) + 1])


@pytest.mark.parametrize("step", ["tree", "commit", "pull"])
def test_a_created_reply_that_cant_be_read_stays_unknown(step: str) -> None:
    git = FakeGit()
    git.answers[step] = httpx.Response(201, text="not json")
    with pytest.raises(UnclearReply) as unclear:
        open_pull(git)
    assert unclear.value.detail == "github_unclear_201"


@pytest.mark.parametrize("step", WRITES)
def test_a_connection_that_never_opened_fails_cleanly(step: str) -> None:
    git = FakeGit()
    git.raises[step] = httpx.ConnectError("arranged")
    with pytest.raises(ToolFailed, match=r"^destination_unreachable$"):
        open_pull(git)


@pytest.mark.parametrize("step", WRITES)
def test_a_reply_lost_after_sending_stays_unknown(step: str) -> None:
    """The write went out, so only a readback can say whether it happened."""
    git = FakeGit()
    git.raises[step] = httpx.ReadError("arranged")
    with pytest.raises(httpx.ReadError):
        open_pull(git)


def test_a_moved_base_goes_back_to_review_and_writes_nothing() -> None:
    git = FakeGit()
    git.heads["main"] = "base-2"
    context = approved("base-1")
    with pytest.raises(ToolFailed, match=r"^base_moved$"):
        open_pull(git, context)
    assert git.writes() == []
    [(tool_id, detail)] = context.returned
    assert tool_id == TOOL_ID and detail["base_sha"] == "base-2"


def test_a_base_that_is_gone_stops_without_a_review() -> None:
    git = FakeGit()
    del git.heads["main"]
    context = approved()
    with pytest.raises(ToolFailed, match=r"^base_moved$"):
        open_pull(git, context)
    assert git.writes() == [] and context.returned == []


def test_a_branch_left_without_a_pull_request_only_opens_the_pull_request() -> None:
    """An earlier attempt pushed the branch and stopped. Its commit is kept, not made again."""
    git = FakeGit()
    git.heads[BRANCH] = "commit-1"
    output = open_pull(git)
    assert git.writes() == ["pull"]
    assert output.head_sha == "commit-1"


def test_an_open_pull_request_from_the_branch_is_returned_without_writing() -> None:
    git = FakeGit()
    open_pull(git)
    before = len(git.writes())
    again = open_pull(git)
    assert len(git.writes()) == before and again.number == 1


def test_an_unclear_pull_list_after_the_branch_stays_unknown() -> None:
    git = FakeGit()
    git.answers["pulls"] = httpx.Response(502)
    with pytest.raises(UnclearReply):
        open_pull(git)
    assert git.writes() == ["tree", "commit", "ref"]


def test_a_readback_with_no_open_pull_request_says_nothing_was_opened() -> None:
    with pytest.raises(NotDelivered):
        read_back(FakeGit())


def test_a_readback_finds_the_pull_request_an_attempt_opened() -> None:
    git = FakeGit()
    opened = open_pull(git)
    assert read_back(git) == opened


def test_a_failed_readback_says_nothing_about_delivery() -> None:
    git = FakeGit()
    git.answers["pulls"] = httpx.Response(500)
    with pytest.raises(UnclearReply):
        read_back(git)


def test_the_review_shows_each_files_diff_against_the_base_head() -> None:
    git = FakeGit()
    detail = review(git)
    assert detail["base_sha"] == "base-1" and detail["base_branch"] == "main"
    files = detail["files"]
    assert isinstance(files, list)
    assert [(item["path"], item["change"]) for item in files] == [
        ("README.md", "modified"),
        ("docs/new.md", "added"),
    ]
    assert "-Hi" in files[0]["diff"] and "+Hello" in files[0]["diff"]
    assert git.writes() == []


def test_a_path_that_is_a_directory_is_refused_in_review() -> None:
    git = FakeGit()
    git.contents["docs/new.md"] = {"type": "dir"}
    with pytest.raises(ToolFailed, match=r"^github_path_not_a_file$"):
        review(git)


def test_a_file_that_isnt_text_is_refused_in_review() -> None:
    git = FakeGit()
    git.contents["README.md"] = {"type": "file", "content": base64.b64encode(b"\xff\xfe").decode()}
    with pytest.raises(ToolFailed, match=r"^github_file_not_text$"):
        review(git)


def test_a_missing_base_branch_is_refused_in_review() -> None:
    git = FakeGit()
    del git.heads["main"]
    with pytest.raises(ToolFailed, match=r"^github_base_not_found$"):
        review(git)


def test_an_attempt_without_its_approved_detail_writes_nothing() -> None:
    git = FakeGit()
    context = Reviewing(None, SCOPE, OPERATION, ApprovedRequest("x", None))
    with pytest.raises(ToolFailed, match=r"^review_detail_missing$"):
        open_pull(git, context)
    assert git.writes() == []


def test_a_directory_listing_is_refused_in_review() -> None:
    """GitHub answers a directory's path with a list of its entries."""
    git = FakeGit()
    git.contents["docs/new.md"] = [{"type": "file", "name": "a.md"}]
    with pytest.raises(ToolFailed, match=r"^github_path_not_a_file$"):
        review(git)


@pytest.mark.parametrize(
    ("step", "status", "code"),
    [
        ("base_head", 503, "github_unavailable"),
        ("base_head", 401, "github_refused_401"),
        ("branch_head", 502, "github_unavailable"),
        ("base_commit", 500, "github_unavailable"),
        ("base_commit", 404, "github_refused_404"),
    ],
)
def test_a_failed_read_before_any_write_is_a_typed_failure(
    step: str, status: int, code: str
) -> None:
    """Every GitHub read maps a status the same way (PADP-04). Nothing was written yet."""
    git = FakeGit()
    git.answers[step] = httpx.Response(status)
    with pytest.raises(ToolFailed, match=rf"^{code}$"):
        open_pull(git)
    assert git.writes() == []


@pytest.mark.parametrize("step", ["base_head", "base_commit"])
def test_a_read_reply_that_cant_be_read_is_malformed_and_writes_nothing(step: str) -> None:
    git = FakeGit()
    git.answers[step] = httpx.Response(200, json={"unexpected": True})
    with pytest.raises(ToolFailed, match=r"^provider_reply_malformed$"):
        open_pull(git)
    assert git.writes() == []


class LaggingPulls(FakeGit):
    """A pull request from the branch exists, but the open list shows it only after `hidden`
    reads, as after a lost reply. GitHub refuses a second one with 422."""

    def __init__(self, hidden: int) -> None:
        super().__init__()
        self.hidden = hidden
        self.answers["pull"] = httpx.Response(
            422, json={"message": "A pull request already exists"}
        )
        self.pulls.append(
            {
                "number": 4,
                "html_url": f"https://github.com/{REPOSITORY}/pull/4",
                "head": {"ref": BRANCH, "sha": "commit-2"},
            }
        )

    def _open(self, request: httpx.Request) -> list[dict[str, object]]:
        if self.hidden:
            self.hidden -= 1
            return []
        return super()._open(request)


def test_a_422_on_the_pull_request_create_is_settled_by_its_open_pull_request() -> None:
    git = LaggingPulls(hidden=1)
    output = open_pull(git)
    assert output.number == 4 and output.branch == BRANCH
    assert git.writes() == ["tree", "commit", "ref", "pull"]


def test_a_422_on_the_pull_request_create_with_none_shown_stays_unknown() -> None:
    """It may be the pull request a lost reply opened, so it is never recorded as failed."""
    git = LaggingPulls(hidden=2)
    with pytest.raises(UnclearReply) as unclear:
        open_pull(git)
    assert unclear.value.detail == "github_unclear_422"


@pytest.mark.parametrize("step", ["tree", "commit", "ref"])
def test_a_422_on_a_git_data_write_is_still_a_refusal(step: str) -> None:
    git = FakeGit()
    git.answers[step] = httpx.Response(422, json={"message": "arranged"})
    with pytest.raises(ToolFailed, match=r"^github_refused_422$"):
        open_pull(git)


def test_a_readback_that_gets_no_reply_stays_unknown_with_its_reason() -> None:
    """Not a failure or a defect: the receipt keeps why nothing could be said."""
    git = FakeGit()
    git.raises["pulls"] = httpx.ReadError("arranged")
    with pytest.raises(UnclearReply) as unclear:
        read_back(git)
    assert unclear.value.detail == "github_unclear_unreachable"


def test_an_empty_repositorys_refs_are_a_refusal_not_an_outage() -> None:
    git = FakeGit()
    git.answers["base_head"] = httpx.Response(409, json={"message": "Git Repository is empty."})
    with pytest.raises(ToolFailed, match=r"^github_refused_409$"):
        open_pull(git)
    assert git.writes() == []


def test_file_content_that_isnt_ascii_base64_is_malformed() -> None:
    git = FakeGit()
    git.contents["README.md"] = {"type": "file", "content": "héllo"}
    with pytest.raises(ToolFailed, match=r"^provider_reply_malformed$"):
        review(git)
