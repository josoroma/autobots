"""US-14.17 and Decision 0024: Tavily and Jina keys from Settings, the environment and .env. JSON cases
through checklib, one scenario at a time (refactor plan R-66, TDBC-06).

Runs on a disposable database with fake transports, so no request leaves this process and every key
is a fixture. A saved key wins over the process environment, which wins over the configuration
root's .env files. Each call resolves its key inside the attempt from the run's workspace. The keys
never reach durable state, a log line or this check's output.
"""

from __future__ import annotations

import io
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import psycopg
from autobots.adapters import tool_registry
from autobots.adapters.jina import jina_tools
from autobots.adapters.tavily import tavily_tools
from autobots.application import tool_switches
from autobots.application.credentials.master_key import create_master_key
from autobots.application.credentials.store import CredentialMissing
from autobots.application.experts import ExpertRefused, create_expert
from autobots.application.provider_settings import InvalidKey, StaleVersion
from autobots.application.runs import admit_run
from autobots.application.tool_catalog import ToolsUnavailable
from autobots.application.tool_definitions import ToolRegistry, ToolScope
from autobots.application.tool_gateway import ToolGateway
from autobots.application.tool_key_settings import ToolKeySettings
from autobots.application.tool_keys import key_sources
from autobots.application.worker_leases import claim_next
from autobots.contracts.experts import ExpertConfig
from autobots.domain.models import resolve_role_policy
from autobots.domain.tool_switches import SwitchKind
from checklib import Cases, run_check, run_scenarios

URL = os.environ["AUTOBOTS_DATABASE_URL"]
WORKSPACE_A = UUID(sys.argv[1])
ENV_TAVILY = "tvly-fixtureProcessEnv0001"
DOTENV_JINA = "jina_fixtureConfigRoot0001"
SAVED_TAVILY = "tvly-fixtureSavedFirst0001"
REPLACED_TAVILY = "tvly-fixtureSavedSecond002"
SAVED_JINA = "jina_fixtureSavedFirst0001"
SAVED_SERPAPI = "serpapi_fixtureSavedFirst01"
SECRETS = (ENV_TAVILY, DOTENV_JINA, SAVED_TAVILY, REPLACED_TAVILY, SAVED_JINA, SAVED_SERPAPI)
seen: list[str] = []


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


class Keys:
    """One connection, the fixture keys' homes, the settings and gateway every scenario calls through, and the
    runs they admitted, which the last scenario scans."""

    def __init__(self, db: Any, cases: Cases) -> None:
        self.db, self.cases = db, cases
        self.runs: list[UUID] = []
        self.search = {"query": "colones", "max_results": 1}
        self.before: dict[str, tuple[str | None, int]] = {}
        self.version = 0

    async def arrange(self) -> None:
        """A master key, a configuration root whose .env holds a Jina key past a blank .env.local, and a second
        workspace. Every log record is kept, so the last scenario can scan it."""
        self.log = io.StringIO()
        handler = logging.StreamHandler(self.log)
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.DEBUG)
        home = Path(tempfile.mkdtemp(prefix="autobots-tool-keys-"))
        key_file = home / "secrets/master.key"
        create_master_key(key_file)
        self.config_root = home / "config"
        self.config_root.mkdir()
        self.dotenv = self.config_root / ".env"
        self.dotenv.write_text(f"JINA_API_KEY={DOTENV_JINA}\nTAVILY_API_KEY=tvly-fixtureLowerThanEnv01\n")
        (self.config_root / ".env.local").write_text("JINA_API_KEY=   \n")
        self.dotenv_before = self.dotenv.read_bytes()
        environ = {
            "TAVILY_API_KEY": ENV_TAVILY,
            "AUTOBOTS_CONFIG_ROOT": str(self.config_root),
            "AUTOBOTS_PROVIDER_MASTER_KEY_FILE": str(key_file),
            "NODE_ENV": "development",
        }
        registry = ToolRegistry()
        for tool in (
            *tavily_tools(httpx.MockTransport(record), environ=environ, resolver=resolve),
            *jina_tools(httpx.MockTransport(record), environ=environ, resolver=resolve),
        ):
            registry.register(tool)
        self.gateway = ToolGateway(registry)
        self.other = uuid4()
        await self.db.execute(
            "insert into public.workspaces (id, name) values (%s, 'Tool keys other')", (self.other,)
        )
        for workspace in (WORKSPACE_A, self.other):
            await self.db.execute(
                "update app_private.provider_credentials set status = 'deleted' "
                "where workspace_id = %s and provider in ('tavily', 'jina', 'serpapi') and status = 'active'",
                (workspace,),
            )
        self.settings = ToolKeySettings(self.db, key_file, environ)

    async def sources(self, workspace: UUID) -> dict[str, tuple[str | None, int]]:
        return {
            state.name: (state.source, state.version)
            for state in await self.settings.status(workspace)
        }

    async def call(
        self, workspace: UUID, tool: str, arguments: dict[str, Any]
    ) -> tuple[str, str | None]:
        await self.db.execute(
            "update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null "
            "where status <> 'done'"
        )
        admitted = await admit_run(
            self.db,
            workspace_id=workspace,
            actor_id=uuid4(),
            idempotency_key=str(uuid4()),
            goal_text="tool keys",
            limit_micro_usd=1000,
            policy=resolve_role_policy(),
        )
        lease = await claim_next(self.db, worker_id="tool-keys", lease_seconds=120)
        assert lease is not None
        scope = ToolScope(workspace, admitted.run_id, lease.generation, {tool: 1}, ("outputs",))
        seen.clear()
        result = await self.gateway.execute(self.db, scope, tool, arguments)
        self.runs.append(admitted.run_id)
        return label(seen[-1] if seen else ""), result.code


async def settings_then_environment_then_dotenv(ctx: Keys) -> None:
    """Settings, then the environment, then .env. Later scenarios read the versions this one sees."""
    call, check, search, sources = ctx.call, ctx.cases.check, ctx.search, ctx.sources
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
    ctx.before = before


async def saves_are_versioned(ctx: Keys) -> None:
    """Owner saves, replaces and removes; a stale version or a malformed value changes nothing."""
    check, settings, sources = ctx.cases.check, ctx.settings, ctx.sources
    before = ctx.before
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
    ctx.version = version


async def keys_resolve_per_attempt(ctx: Keys) -> None:
    """Resolved per attempt from the run's workspace, and a replacement applies with no restart."""
    call, check, other, search, settings = ctx.call, ctx.cases.check, ctx.other, ctx.search, ctx.settings
    version = ctx.version
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


async def removing_falls_back_to_dotenv(ctx: Keys) -> None:
    """Removing falls back to the environment, and never edits .env."""
    call, check, dotenv, dotenv_before, search, settings, sources = ctx.call, ctx.cases.check, ctx.dotenv, ctx.dotenv_before, ctx.search, ctx.settings, ctx.sources
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


async def availability_admission_and_save_agree(ctx: Keys) -> None:
    """Availability, admission and save follow the same order, for the request's workspace."""
    check, config_root, db, other = ctx.cases.check, ctx.config_root, ctx.db, ctx.other
    bare = {"AUTOBOTS_CONFIG_ROOT": str(config_root / "missing"), "NODE_ENV": "development"}
    view_a = await key_sources(db, WORKSPACE_A, bare)
    view_other = await key_sources(db, other, bare)
    catalog_a = {
        tool.tool_id: (
            tool.availability,
            tool.key_requirement.source if tool.key_requirement else None,
        )
        for tool in tool_registry.catalog().catalog(view_a).tools
    }
    catalog_other = {tool.tool_id: tool.availability for tool in tool_registry.catalog().catalog(view_other).tools}
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
            tool_registry.catalog().require_available(["tavily_search"], view)
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
                catalog=tool_registry.catalog(),
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


async def sealed_keys_stay_out_of_durable_state(ctx: Keys) -> None:
    """The sealed key stays out of durable state, its logs and this output."""
    check, db, log, runs = ctx.cases.check, ctx.db, ctx.log, ctx.runs
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


# In order: saves_are_versioned and keys_resolve_per_attempt read the versions the scenario before them saw.
async def serpapi_key_is_a_keys_and_vars_secret(ctx: Keys) -> None:
    """US-14.22, Decision 0032 G7: the SerpApi key is a sixth item, a secret saved, sealed and
    removed like the others, and google_search's availability follows it per workspace."""
    check, config_root, db, other, settings = ctx.cases.check, ctx.config_root, ctx.db, ctx.other, ctx.settings
    listed = await settings.status(WORKSPACE_A)
    names = [(state.name, state.kind) for state in listed]
    check(
        "Keys & vars lists the SerpApi key as a secret after the Jina key",
        "tavily, jina, serpapi as secrets, then the GitHub items",
        names,
        names[:4] == [("tavily", "secret"), ("jina", "secret"), ("serpapi", "secret"), ("github_token", "secret")],
    )
    before = {state.name: state for state in listed}["serpapi"]
    await settings.save(WORKSPACE_A, "serpapi", SAVED_SERPAPI, before.version)
    saved = {state.name: state for state in await settings.status(WORKSPACE_A)}["serpapi"]
    rows = await (await db.execute(
        "select ciphertext from app_private.provider_credentials "
        "where workspace_id = %s and provider = 'serpapi' and status = 'active'",
        (WORKSPACE_A,),
    )).fetchall()
    sealed = len(rows) == 1 and SAVED_SERPAPI.encode() not in bytes(rows[0][0])
    check(
        "a saved SerpApi key is sealed and never returned",
        "source settings, no value, one sealed row",
        (saved.source, saved.value, len(rows), sealed),
        saved.source == "settings" and saved.value is None and sealed,
    )
    bare = {"AUTOBOTS_CONFIG_ROOT": str(config_root / "missing"), "NODE_ENV": "development"}
    found_a = {
        tool.tool_id: (tool.availability, tool.key_requirement.source if tool.key_requirement else None)
        for tool in tool_registry.catalog().catalog(await key_sources(db, WORKSPACE_A, bare)).tools
    }
    found_other = {
        tool.tool_id: tool.availability
        for tool in tool_registry.catalog().catalog(await key_sources(db, other, bare)).tools
    }
    check(
        "google_search is available from Settings in its workspace and key_missing in another",
        "available from settings; key_missing",
        (found_a.get("google_search"), found_other.get("google_search")),
        found_a.get("google_search") == ("available", "settings") and found_other.get("google_search") == "key_missing",
    )
    # Migration 63 widened both lists to serpapi only: any other provider is still refused.
    refused: list[str] = []
    for statement, values in (
        ("insert into app_private.tool_key_settings (workspace_id, provider) values (%s, 'serper')", (other,)),
        (
            "insert into app_private.provider_credentials (credential_id, version, workspace_id, provider, ciphertext, "
            "nonce, tag, key_version, status) values (%s, 1, %s, 'serper', '\\x00', %s, %s, 1, 'deleted')",
            (uuid4(), other, bytes(12), bytes(16)),
        ),
    ):
        try:
            async with db.transaction():
                await db.execute(statement, values)
            refused.append("accepted")
        except psycopg.errors.CheckViolation:
            refused.append("check_violation")
    check(
        "both provider lists accept serpapi and still refuse an unknown provider",
        "serpapi saved above; serper refused by both checks",
        refused,
        refused == ["check_violation", "check_violation"],
    )
    await settings.remove(WORKSPACE_A, "serpapi", saved.version)
    removed = {state.name: state for state in await settings.status(WORKSPACE_A)}["serpapi"]
    check(
        "removing the SerpApi key falls back to the next source, here none",
        "source none",
        removed.source,
        removed.source is None,
    )


async def tool_switches_follow_the_workspace(ctx: Keys) -> None:
    """US-14.24, Decision 0033 W1 to W4: the owner's switches turn a tool, or its group, off for one workspace, for the
    catalog, admission and Expert saves, at an expected version."""
    check, config_root, db, other, settings = ctx.cases.check, ctx.config_root, ctx.db, ctx.other, ctx.settings
    serpapi = {state.name: state for state in await settings.status(WORKSPACE_A)}["serpapi"]
    await settings.save(WORKSPACE_A, "serpapi", SAVED_SERPAPI, serpapi.version)
    bare = {"AUTOBOTS_CONFIG_ROOT": str(config_root / "missing"), "NODE_ENV": "development"}

    async def tools(workspace: UUID) -> dict[str, tuple[str, str | None]]:
        view = await key_sources(db, workspace, bare)
        return {item.tool_id: (item.availability, item.availability_reason) for item in tool_registry.catalog().catalog(view).tools}

    async def flip(kind: SwitchKind, target: str, enabled: bool) -> tool_switches.Switch:
        """At the switch's current version, since another check may have changed it already."""
        current = (await tool_switches.load(db, WORKSPACE_A)).get((kind, target), tool_switches.Switch())
        return await tool_switches.change(db, WORKSPACE_A, kind, target, enabled, current.version)

    before = await tools(WORKSPACE_A)
    google = ("google_search", "google_map", "google_extract", "google_crawl")
    check("with nothing switched, the four Google tools are available in the workspace", "all available",
          [before.get(tool) for tool in google], all(before.get(tool) == ("available", None) for tool in google))
    turned = await flip("tool", "google_crawl", False)
    stale: list[str] = []
    try:
        await tool_switches.change(db, WORKSPACE_A, "tool", "google_crawl", True, turned.version - 1)
        stale.append("saved")
    except StaleVersion as refused:
        stale.append(refused.code)
    first, second = await tools(WORKSPACE_A), await tools(other)
    check("turning google_crawl off disables it in its workspace only, and a stale change is refused",
          "turned_off here; not turned off elsewhere; stale_version",
          (turned, first.get("google_crawl"), second.get("google_crawl"), stale),
          turned.enabled is False and first.get("google_crawl") == ("disabled_by_policy", "turned_off")
          and (second.get("google_crawl") or ("", ""))[1] != "turned_off" and stale == ["stale_version"])
    await flip("group", "google", False)
    await flip("tool", "google_search", True)
    grouped = await tools(WORKSPACE_A)
    check("turning the Google group off turns off all four, even google_search switched on by itself", "group_turned_off x4",
          [grouped.get(tool) for tool in google], all(grouped.get(tool) == ("disabled_by_policy", "group_turned_off") for tool in google))
    refusals: list[str] = []
    try:
        tool_registry.catalog().require_available(["google_search"], await key_sources(db, WORKSPACE_A, bare))
        refusals.append("admitted")
    except ToolsUnavailable as refused:
        refusals.append(refused.code)
    try:
        await create_expert(db, workspace_id=WORKSPACE_A, actor_id=uuid4(), idempotency_key=str(uuid4()),
                            name=f"Google reader {uuid4().hex[:6]}", config=ExpertConfig(tools=["google_search"]),
                            catalog=tool_registry.catalog())
        refusals.append("saved")
    except ExpertRefused as refused:
        refusals.append(refused.code)
    check("admission and an Expert save refuse a tool that is off", "['tool_unavailable', 'expert_tool_unavailable']",
          refusals, refusals == ["tool_unavailable", "expert_tool_unavailable"])
    await flip("group", "google", True)
    await flip("tool", "google_crawl", True)
    after = await tools(WORKSPACE_A)
    check("turning the group and google_crawl back on makes all four available again", "all available",
          [after.get(tool) for tool in google], all(after.get(tool) == ("available", None) for tool in google))
    privileges = await (await db.execute(
        "select has_table_privilege('anon', 'app_private.tool_switches', 'select'), "
        "has_table_privilege('authenticated', 'app_private.tool_switches', 'select'), "
        "has_table_privilege('autobots_runtime', 'app_private.tool_switches', 'select'), "
        "has_table_privilege('autobots_runtime', 'app_private.tool_switches', 'insert'), "
        "has_table_privilege('autobots_runtime', 'app_private.tool_switches', 'update'), "
        "has_table_privilege('autobots_runtime', 'app_private.tool_switches', 'delete')"
    )).fetchone()
    check("the switch table is private: no anon or authenticated access, and the runtime role reads, inserts and updates only",
          "(False, False, True, True, True, False)", privileges, tuple(privileges or ()) == (False, False, True, True, True, False))
    removing = {state.name: state for state in await settings.status(WORKSPACE_A)}["serpapi"]
    await settings.remove(WORKSPACE_A, "serpapi", removing.version)


SCENARIOS = (
    settings_then_environment_then_dotenv,
    saves_are_versioned,
    keys_resolve_per_attempt,
    removing_falls_back_to_dotenv,
    availability_admission_and_save_agree,
    serpapi_key_is_a_keys_and_vars_secret,
    tool_switches_follow_the_workspace,
    sealed_keys_stay_out_of_durable_state,
)


async def main(cases: Cases) -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        context = Keys(db, cases)
        await context.arrange()
        await run_scenarios(cases, SCENARIOS, context)


if __name__ == "__main__":
    # A fixture key that reached this output fails the check and is never printed (AGENTS.md).
    # Its parent's Child entry in scripts/app_db.py gives it 180 seconds.
    run_check(main, secrets=SECRETS, parent_timeout=180)
