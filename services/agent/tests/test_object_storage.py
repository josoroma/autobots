"""Supabase Storage over a fake transport (refactor plan R-62, PADP-05 and PADP-18).

The service key bypasses Storage's own rules, so every path stays inside a workspace and run
namespace, and each status maps to one answer. The disposable checks run it against real Storage.
"""

import asyncio
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from autobots.adapters.object_storage import BUCKET, StorageUnavailable, SupabaseObjectStore

KEY = "arranged-service-key"
RUN_PATH = f"{uuid4()}/{uuid4()}"
OBJECT = f"{RUN_PATH}/report.md"


class Storage:
    def __init__(self, status: int = 200, body: bytes = b"") -> None:
        self.status = status
        self.body = body
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status, content=self.body)


def store(storage: Storage) -> SupabaseObjectStore:
    return SupabaseObjectStore(
        "http://storage.invalid/", SecretStr(KEY), transport=httpx.MockTransport(storage)
    )


@pytest.mark.parametrize(
    "path",
    [
        "report.md",
        f"{uuid4()}/report.md",
        f"{RUN_PATH}/../other",
        f"{RUN_PATH}/nested/deeper",
        f"../{RUN_PATH}",
        f"{RUN_PATH}/a b",
    ],
)
def test_a_path_outside_a_run_namespace_is_refused_before_any_request(path: str) -> None:
    storage = Storage()
    with pytest.raises(ValueError, match="namespace"):
        asyncio.run(store(storage).get(path))
    assert storage.requests == []


def test_each_request_carries_the_service_key_to_its_bucket_only() -> None:
    storage = Storage(200, b"body")
    assert asyncio.run(store(storage).get(OBJECT)) == b"body"
    [request] = storage.requests
    assert str(request.url) == f"http://storage.invalid/storage/v1/object/{BUCKET}/{OBJECT}"
    assert request.headers["apikey"] == KEY
    assert request.headers["authorization"] == f"Bearer {KEY}"


def test_an_existing_object_is_never_overwritten() -> None:
    created = Storage(200)
    assert asyncio.run(store(created).put(OBJECT, b"x", "text/markdown")) is True
    assert created.requests[0].headers["x-upsert"] == "false"
    assert created.requests[0].headers["content-type"] == "text/markdown"
    exists = Storage(409, b'{"message": "The resource already exists"}')
    assert asyncio.run(store(exists).put(OBJECT, b"x", "text/markdown")) is False


@pytest.mark.parametrize("status", [409, 500, 503])
def test_an_upload_storage_couldnt_take_is_unavailable(status: int) -> None:
    with pytest.raises(StorageUnavailable):
        asyncio.run(store(Storage(status, b"{}")).put(OBJECT, b"x", "text/markdown"))


@pytest.mark.parametrize(("status", "found"), [(404, None), (400, None)])
def test_a_missing_object_reads_as_none(status: int, found: bytes | None) -> None:
    assert asyncio.run(store(Storage(status)).get(OBJECT)) is found


@pytest.mark.parametrize("status", [301, 500, 502])
def test_any_other_status_is_unavailable_and_says_nothing_about_the_object(status: int) -> None:
    with pytest.raises(StorageUnavailable):
        asyncio.run(store(Storage(status)).get(OBJECT))


def test_removal_tolerates_an_object_already_gone() -> None:
    for status in (200, 400, 404):
        asyncio.run(store(Storage(status)).remove(OBJECT))
    with pytest.raises(StorageUnavailable):
        asyncio.run(store(Storage(500)).remove(OBJECT))


def test_a_listing_names_full_paths_under_the_run() -> None:
    storage = Storage(200, b'[{"name": "a.md"}, {"name": "b.csv"}]')
    assert asyncio.run(store(storage).names(RUN_PATH)) == [f"{RUN_PATH}/a.md", f"{RUN_PATH}/b.csv"]
    assert asyncio.run(store(Storage(200)).ping()) is None
    with pytest.raises(StorageUnavailable):
        asyncio.run(store(Storage(503)).ping())
