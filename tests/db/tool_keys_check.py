"""US-14.17 and Decision 0024: Tavily and Jina keys from Settings, the environment and .env. JSON cases.

Runs on a disposable database with fake transports, so no request leaves this process and every key
is a fixture. A saved key wins over the process environment, which wins over the configuration
root's .env files. Each call resolves its key inside the attempt from the run's workspace. The keys
never reach durable state, a log line or this check's output.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import psycopg
from autobots.adapters.jina import jina_tools
from autobots.adapters.tavily import tavily_tools
from autobots.application.credentials.master_key import create_master_key
from autobots.application.credentials.store import CredentialMissing
from autobots.application.experts import ExpertRefused, create_expert
from autobots.application.provider_settings import InvalidKey, StaleVersion
from autobots.application.runs import admit_run
from autobots.application.tool_catalog import ToolsUnavailable, require_available, tool_catalog
from autobots.application.tool_gateway import ToolGateway, ToolRegistry, ToolScope
from autobots.application.tool_key_settings import ToolKeySettings
from autobots.application.tool_keys import key_sources
from autobots.application.worker_leases import claim_next
from autobots.contracts.experts import ExpertConfig
from autobots.domain.models import resolve_role_policy

URL = os.environ["AUTOBOTS_DATABASE_URL"]
WORKSPACE_A = UUID(sys.argv[1])
ENV_TAVILY = "tvly-fixtureProcessEnv0001"
DOTENV_JINA = "jina_fixtureConfigRoot0001"
SAVED_TAVILY = "tvly-fixtureSavedFirst0001"
REPLACED_TAVILY = "tvly-fixtureSavedSecond002"
SAVED_JINA = "jina_fixtureSavedFirst0001"
SECRETS = (ENV_TAVILY, DOTENV_JINA, SAVED_TAVILY, REPLACED_TAVILY, SAVED_JINA)
cases: list[dict[str, Any]] = []
seen: list[str] = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append(
        {"id": name, "expected": expected, "observed": str(observed)[:700], "passed": bool(passed)}
    )


def record(request: httpx.Request) -> httpx.Response:
    seen.append(request.headers.get("Authorization", "").removeprefix("Bearer "))
    if request.url.host == "api.tavily.com":
        return httpx.Response(
            200,
            json={"results": [{"title": "A", "url": "https://example.com/a", "content": "text"}]},
        )
    return httpx.Response(
        200, json={"data": [{"title": "A", "url": "https://example.com/a", "description": "text"}]}
    )


async def resolve(host: str, _: int) -> list[str]:
    return ["93.184.215.14"]


def label(key: str) -> str:
    """Which fixture a request carried, named without its value, so this output holds no key."""
    names = {
        ENV_TAVILY: "environment Tavily",
        DOTENV_JINA: ".env Jina",
        SAVED_TAVILY: "first saved Tavily",
        REPLACED_TAVILY: "replacement Tavily",
        SAVED_JINA: "saved Jina",
    }
    return names.get(key, "unknown" if key else "none")


async def main() -> None:
    log = io.StringIO()
    handler = logging.StreamHandler(log)
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.DEBUG)
    home = Path(tempfile.mkdtemp(prefix="autobots-tool-keys-"))
    key_file = home / "secrets/master.key"
    create_master_key(key_file)
    config_root = home / "config"
    config_root.mkdir()
    dotenv = config_root / ".env"
    dotenv.write_text(f"JINA_API_KEY={DOTENV_JINA}\nTAVILY_API_KEY=tvly-fixtureLowerThanEnv01\n")
    (config_root / ".env.local").write_text("JINA_API_KEY=   \n")
    dotenv_before = dotenv.read_bytes()
    environ = {
        "TAVILY_API_KEY": ENV_TAVILY,
        "AUTOBOTS_CONFIG_ROOT": str(config_root),
        "AUTOBOTS_PROVIDER_MASTER_KEY_FILE": str(key_file),
        "NODE_ENV": "development",
    }
    registry = ToolRegistry()
    for tool in (
        *tavily_tools(httpx.MockTransport(record), environ=environ, resolver=resolve),
        *jina_tools(httpx.MockTransport(record), environ=environ, resolver=resolve),
    ):
        registry.register(tool)
    gateway = ToolGateway(registry)
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        other = uuid4()
        await db.execute(
            "insert into public.workspaces (id, name) values (%s, 'Tool keys other')", (other,)
        )
        for workspace in (WORKSPACE_A, other):
            await db.execute(
                "update app_private.provider_credentials set status = 'deleted' "
                "where workspace_id = %s and provider in ('tavily', 'jina') and status = 'active'",
                (workspace,),
            )
        settings = ToolKeySettings(db, key_file, environ)

        async def sources(workspace: UUID) -> dict[str, tuple[str | None, int]]:
            return {
                state.name: (state.source, state.version)
                for state in await settings.status(workspace)
            }

        async def call(
            workspace: UUID, tool: str, arguments: dict[str, Any]
        ) -> tuple[str, str | None]:
            await db.execute(
                "update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null "
                "where status <> 'done'"
            )
            admitted = await admit_run(
                db,
                workspace_id=workspace,
                actor_id=uuid4(),
                idempotency_key=str(uuid4()),
                goal_text="tool keys",
                limit_micro_usd=1000,
                policy=resolve_role_policy(),
            )
            lease = await claim_next(db, worker_id="tool-keys", lease_seconds=120)
            assert lease is not None
            scope = ToolScope(workspace, admitted.run_id, lease.generation, {tool: 1}, ("outputs",))
            seen.clear()
            result = await gateway.execute(db, scope, tool, arguments)
            runs.append(admitted.run_id)
            return label(seen[-1] if seen else ""), result.code

        runs: list[UUID] = []
        search = {"query": "colones", "max_results": 1}

        # Settings, then the environment, then .env.
        before = await sources(WORKSPACE_A)
        check(
            "with nothing saved, Tavily comes from the environment and Jina from .env, past a blank .env.local",
            "tavily environment, jina environment",
            before,
            before["tavily"][0] == "environment" and before["jina"][0] == "environment",
        )
        first = await call(WORKSPACE_A, "tavily_search", search)
        jina_first = await call(WORKSPACE_A, "search_web", search)
        check(
            "the process environment wins over .env, and .env is read past a blank value",
            "environment Tavily, .env Jina",
            (first, jina_first),
            first == ("environment Tavily", None) and jina_first == (".env Jina", None),
        )

        # Owner saves, replaces and removes; a stale version or a malformed value changes nothing.
        version = before["tavily"][1]
        await settings.save(WORKSPACE_A, "tavily", SAVED_TAVILY, version)
        stale: str | None = None
        try:
            await settings.save(WORKSPACE_A, "tavily", REPLACED_TAVILY, version)
        except StaleVersion as error:
            stale = error.code
        malformed: str | None = None
        try:
            await settings.save(WORKSPACE_A, "tavily", "has a space", version + 1)
        except InvalidKey as error:
            malformed = error.code
        after = await sources(WORKSPACE_A)
        check(
            "a save advances the version, and a stale or malformed one is refused",
            "settings, version +1, stale_version, invalid_key",
            (after["tavily"], stale, malformed),
            after["tavily"] == ("settings", version + 1)
            and stale == "stale_version"
            and malformed == "invalid_key",
        )

        # Resolved per attempt from the run's workspace, and a replacement applies with no restart.
        saved = await call(WORKSPACE_A, "tavily_search", search)
        elsewhere = await call(other, "tavily_search", search)
        check(
            "each workspace calls with its own key: saved for one, the environment for the other",
            "first saved Tavily, environment Tavily",
            (saved, elsewhere),
            saved == ("first saved Tavily", None) and elsewhere == ("environment Tavily", None),
        )
        await settings.save(WORKSPACE_A, "tavily", REPLACED_TAVILY, version + 1)
        replaced = await call(WORKSPACE_A, "tavily_search", search)
        check(
            "a replaced key is used by the next call, with the same registry and no restart",
            "replacement Tavily",
            replaced,
            replaced == ("replacement Tavily", None),
        )

        # Removing falls back to the environment, and never edits .env.
        jina_version = (await sources(WORKSPACE_A))["jina"][1]
        await settings.save(WORKSPACE_A, "jina", SAVED_JINA, jina_version)
        jina_saved = await call(WORKSPACE_A, "search_web", search)
        await settings.remove(WORKSPACE_A, "jina", jina_version + 1)
        jina_removed = await call(WORKSPACE_A, "search_web", search)
        after_remove = await sources(WORKSPACE_A)
        nothing: str | None = None
        try:
            await settings.remove(WORKSPACE_A, "jina", jina_version + 2)
        except CredentialMissing as error:
            nothing = error.code
        check(
            "removing the saved Jina key falls back to .env, which is byte-for-byte unchanged",
            "saved Jina, then .env Jina, source environment, file unchanged",
            (
                jina_saved,
                jina_removed,
                after_remove["jina"],
                nothing,
                dotenv.read_bytes() == dotenv_before,
            ),
            jina_saved == ("saved Jina", None)
            and jina_removed == (".env Jina", None)
            and after_remove["jina"] == ("environment", jina_version + 2)
            and nothing == "credential_missing"
            and dotenv.read_bytes() == dotenv_before,
        )

        # Availability, admission and save follow the same order, for the request's workspace.
        bare = {"AUTOBOTS_CONFIG_ROOT": str(config_root / "missing"), "NODE_ENV": "development"}
        view_a = await key_sources(db, WORKSPACE_A, bare)
        view_other = await key_sources(db, other, bare)
        catalog_a = {
            tool.tool_id: (
                tool.availability,
                tool.key_requirement.source if tool.key_requirement else None,
            )
            for tool in tool_catalog(view_a).tools
        }
        catalog_other = {tool.tool_id: tool.availability for tool in tool_catalog(view_other).tools}
        check(
            "the catalog follows the workspace: a saved key is available from Settings, none is key_missing",
            "tavily_search available from settings in A, key_missing elsewhere; search_web key_missing in both",
            (
                catalog_a.get("tavily_search"),
                catalog_other.get("tavily_search"),
                catalog_a.get("search_web"),
            ),
            catalog_a.get("tavily_search") == ("available", "settings")
            and catalog_other.get("tavily_search") == "key_missing"
            and catalog_a.get("search_web") == ("key_missing", None),
        )
        admitted: list[str] = []
        for _workspace, view in ((WORKSPACE_A, view_a), (other, view_other)):
            try:
                require_available(["tavily_search"], view)
                admitted.append("admitted")
            except ToolsUnavailable as refused:
                admitted.append(refused.code)
        check(
            "run and routine admission (both call require_available with the workspace view) agree",
            "['admitted', 'tool_unavailable']",
            admitted,
            admitted == ["admitted", "tool_unavailable"],
        )
        saved_expert: list[str] = []
        for workspace in (WORKSPACE_A, other):
            try:
                await create_expert(
                    db,
                    workspace_id=workspace,
                    actor_id=uuid4(),
                    idempotency_key=str(uuid4()),
                    name=f"Tavily reader {uuid4().hex[:6]}",
                    config=ExpertConfig(tools=["tavily_search"]),
                )
                saved_expert.append("saved")
            except ExpertRefused as refused:
                saved_expert.append(refused.code)
        check(
            "saving an Expert that grants tavily_search follows each workspace's key (this process has no Tavily variable)",
            "['saved', 'expert_tool_unavailable']",
            saved_expert,
            saved_expert == ["saved", "expert_tool_unavailable"],
        )

        # The sealed key stays out of durable state.
        texts: list[str] = []
        for query in (
            "select t::text from app_private.tool_uses t where run_id = any(%s)",
            "select t::text from app_private.tool_receipts t where run_id = any(%s)",
            "select t::text from public.run_events t where run_id = any(%s)",
            "select t::text from public.runs t where id = any(%s)",
            "select t::text from app_private.run_jobs t where run_id = any(%s)",
            "select t::text from agent_runtime.checkpoints t where thread_id = any(%s::text[])",
        ):
            cursor = await db.execute(
                query, ([str(run) for run in runs] if "thread_id" in query else runs,)
            )
            texts += [str(row[0]) for row in await cursor.fetchall()]
        cursor = await db.execute(
            "select count(*) filter (where position(convert_to(%s, 'utf8') in ciphertext) > 0 "
            "or position(convert_to(%s, 'utf8') in ciphertext) > 0), count(*) "
            "from app_private.provider_credentials where workspace_id = %s and provider in ('tavily', 'jina')",
            (REPLACED_TAVILY, SAVED_JINA, WORKSPACE_A),
        )
        plain, rows = await cursor.fetchone()
        leaked = [
            label(secret)
            for secret in SECRETS
            if any(secret in text for text in texts) or secret in log.getvalue()
        ]
        check(
            "no key appears in tool uses, receipts, events, runs, jobs, checkpoints or logs, and rows hold ciphertext only",
            "nothing leaked, 0 plaintext rows",
            (leaked, len(texts), plain, rows),
            leaked == [] and len(texts) > 0 and plain == 0 and rows >= 3,
        )
    output = json.dumps({"cases": cases})
    if any(secret in output for secret in SECRETS):
        raise SystemExit("a fixture key reached this check output")
    print(output)


asyncio.run(main())
