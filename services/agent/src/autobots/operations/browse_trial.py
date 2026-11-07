"""The one live browse trial on Sol: US-14.16 and Decision 0019 S6.

The owner authorized it once, capped at US$1. This process reads only `OPENROUTER_API_KEY` from
the key file it is given, as the route qualification does, and nothing prints it.

The run gets an Expert granting `browse_goal`, no model choice (so `researcher` freezes on Sol) and
a US$1 budget. Its one call goes through the real gateway, approval, loop middleware, admission
and isolated executor. Each step's model comes from the shared factory (`chat_model` over the SDK
client, with `require_parameters` and no fallbacks) for the researcher's prepared attempt, from a
fresh catalog. Only the key comes from the file rather than the workspace's stored credential.

A recorded trial refuses to run again without `--owner-requested-repeat`, before anything starts.
It runs in no verification profile.
"""

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import SecretStr

from autobots.adapters import loop_middleware
from autobots.adapters.browser_executor import BrowserExecutor, BrowserSession
from autobots.adapters.loop_middleware import LoopMiddleware, ModelRoute
from autobots.adapters.models.catalog import CatalogSnapshot, parse_catalog, validated_entry
from autobots.adapters.models.factory import chat_model
from autobots.adapters.models.openrouter_metadata import catalog_fetcher
from autobots.application.worker_inference import prepared
from autobots.domain.models import ModelProfileId, ModelRole, RolePolicy
from autobots.operations.logs import configure_logging, forbid_remote_tracing
from autobots.operations.route_qualification import Refused, read_key

ROLE = ModelRole.RESEARCHER
LIMIT_MICRO_USD = 1_000_000
START_URL = "https://example.com/"
DOMAINS = ["example.com", "iana.org"]
TASK = (
    "Find out what example.com is for and which organisation maintains it. Read only what you "
    "need, then finish with a short summary."
)
RESULT = "result.json"


def refuse_repeat(out: Path, owner_requested: bool) -> None:
    """S6: once. Any recorded start counts, even one that ended before a call was answered."""
    if (out / RESULT).exists() and not owner_requested:
        raise Refused("this trial already ran; a repeat needs the owner's request")


class TrialModel:
    """The researcher's model, one call at a time, from the shared factory and a fresh catalog."""

    def __init__(
        self,
        payload: Mapping[str, Any],
        policy: RolePolicy,
        key: SecretStr,
        make_client: Callable[[str], Any] | None = None,
        tools: Any = None,
        options: Mapping[str, Any] | None = None,
    ) -> None:
        self._payload = payload
        self._policy = policy
        self._key = key
        self._make_client = make_client
        self._tools = tools
        self._options = dict(options or {})

    def catalog(self) -> CatalogSnapshot:
        return parse_catalog(self._payload, retrieved_at=datetime.now(UTC), revision="trial")

    def route(self) -> ModelRoute:
        catalog = self.catalog()
        _, worst = prepared(self._policy, catalog, ROLE)
        profile = self._policy.profile_for(ROLE)
        entry = validated_entry(profile, catalog, datetime.now(UTC))
        rate = entry.pricing.input_per_million if entry.pricing else 0
        tier = entry.pricing.tier_from_tokens if entry.pricing else None
        return ModelRoute(ROLE.value, profile.id.value, profile.wire_id, worst, rate, tier)

    def bind_tools(self, tools: Any, **options: Any) -> "TrialModel":
        return TrialModel(self._payload, self._policy, self._key, self._make_client, tools, options)

    async def ainvoke(self, messages: Any, stop: Any = None, **kwargs: Any) -> Any:
        attempt, _ = prepared(self._policy, self.catalog(), ROLE)
        client: Any = chat_model(attempt, self._key, client_factory=self._make_client)
        if self._tools is not None:
            client = client.bind_tools(self._tools, **self._options)
        return await client.ainvoke(messages, stop=stop, **kwargs)


class TrialExecutor(BrowserExecutor):
    """Keeps the proxy's log of hosts before the session is removed. Hosts, never paths."""

    def __init__(self) -> None:
        super().__init__()
        self.log: list[dict[str, Any]] = []

    async def stop(self, session: BrowserSession) -> None:
        if not self.log:
            try:
                self.log = await self.proxy_log(session)
            except Exception:  # The record is best effort; removal isn't.
                self.log = [{"event": "log_unavailable"}]
        await super().stop(session)


def _write(out: Path, record: Mapping[str, Any]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    text = json.dumps(record, indent=2, ensure_ascii=False, default=str)
    (out / RESULT).write_text(text + "\n")


def hosts(log: list[dict[str, Any]]) -> dict[str, list[str]]:
    connected = sorted({str(entry.get("host")) for entry in log if entry.get("event") == "allowed"})
    refused = sorted(
        {
            f"{entry.get('host')}:{entry.get('event')}"
            for entry in log
            if entry.get("event") not in ("allowed", None)
        }
    )
    return {"connected": connected, "refused": refused}


def inside(host: str) -> bool:
    return any(host == domain or host.endswith("." + domain) for domain in DOMAINS)


async def run_trial(
    database_url: str,
    workspace: UUID,
    key: SecretStr,
    out: Path,
    payload: Mapping[str, Any],
    make_client: Callable[[str], Any] | None = None,
    executor: TrialExecutor | None = None,
) -> dict[str, Any]:
    import psycopg

    from autobots.application import browsing_tool
    from autobots.application.approvals import decide
    from autobots.application.experts import create_expert
    from autobots.application.run_usage import RootLimits, ensure_usage
    from autobots.application.runs import admit_run
    from autobots.application.tool_gateway import ToolGateway, ToolRegistry, ToolScope
    from autobots.application.worker_inference import frozen_policy
    from autobots.application.worker_leases import claim_next
    from autobots.contracts.experts import ExpertConfig
    from autobots.domain.models import resolve_role_policy
    from autobots.domain.tools import PLAN_TOOLS

    os.environ[browsing_tool.ENABLE] = "enabled"
    if not browsing_tool.executor_ready():
        raise Refused("the executor isn't qualified at the current code")
    executor = executor or TrialExecutor()
    actor = uuid4()
    grant = {**PLAN_TOOLS, "browse_goal": 1}
    async with await psycopg.AsyncConnection.connect(database_url, autocommit=True) as db:
        expert = await create_expert(
            db,
            workspace_id=workspace,
            actor_id=actor,
            idempotency_key=str(uuid4()),
            name=f"Browse trial {uuid4().hex[:6]}",
            config=ExpertConfig(tools=["browse_goal"]),
        )
        binding = type(
            "Binding",
            (),
            {
                "session_id": None,
                "expert_id": expert.id,
                "version": 1,
                "instructions": "",
                "tools": grant,
            },
        )()
        admitted = await admit_run(
            db,
            workspace_id=workspace,
            actor_id=actor,
            idempotency_key=str(uuid4()),
            goal_text="Live browse trial",
            limit_micro_usd=LIMIT_MICRO_USD,
            policy=resolve_role_policy(),
            binding=binding,
        )
        run = admitted.run_id
        cursor = await db.execute("select policy_snapshot from public.runs where id = %s", (run,))
        found = await cursor.fetchone()
        if found is None:
            raise Refused("the trial's run wasn't stored")
        snapshot = found[0]
        if snapshot["bindings"].get(ROLE.value) != ModelProfileId.SOL.value:
            raise Refused("the run's researcher route isn't frozen on Sol")
        policy = frozen_policy(snapshot)
        model = TrialModel(payload, policy, key, make_client)
        route = model.route()
        await ensure_usage(db, run)

        async def claimed() -> ToolScope:
            lease = await claim_next(db, worker_id="browse-trial", lease_seconds=900)
            if lease is None or lease.run_id != run:
                raise Refused("the trial's run wasn't the one claimed")
            await db.execute("update public.runs set status = 'running' where id = %s", (run,))
            return ToolScope(workspace, run, lease.generation, grant)

        arguments = {
            "task": TASK,
            "start_url": START_URL,
            "allowed_domains": DOMAINS,
            "max_steps": 8,
            "max_seconds": 240,
        }

        async def execute(scope: ToolScope) -> Any:
            registry = ToolRegistry()
            runtime = browsing_tool.BrowsingRuntime(executor, model, route)
            registry.register(browsing_tool.browse_tool(runtime))
            middleware = LoopMiddleware(db, scope, RootLimits(), route)
            token = loop_middleware._MIDDLEWARE.set(middleware)
            try:
                return await ToolGateway(registry).execute(db, scope, "browse_goal", arguments)
            finally:
                loop_middleware._MIDDLEWARE.reset(token)

        pending = await execute(await claimed())
        if pending.code != "approval_pending":
            raise Refused(f"the call didn't wait for approval: {pending.code}")
        row = await (
            await db.execute(
                "select id, argument_hash from public.approval_requests where run_id = %s",
                (run,),
            )
        ).fetchone()
        if row is None:
            raise Refused("no approval request was stored")
        await decide(
            db,
            workspace_id=workspace,
            actor_id=actor,
            approval_id=row[0],
            idempotency_key=str(uuid4()),
            decision="approve",
            argument_hash=row[1],
        )
        scope = await claimed()
        # Recorded before the first paid call, so even a crash counts as the one trial.
        _write(out, {"status": "started", "run_id": str(run)})
        result = await execute(scope)
        invocations = await (
            await db.execute(
                "select role, profile, wire_id, status, reserved_micro_usd, charged_micro_usd, "
                "finish_reason, input_tokens, output_tokens, tool_names, upstream_provider "
                "from app_private.model_invocations where run_id = %s order by attempt",
                (run,),
            )
        ).fetchall()
        uses = await (
            await db.execute(
                "select outcome, code, metered, input_public, output_public from "
                "app_private.tool_uses where run_id = %s order by sequence_in_run",
                (run,),
            )
        ).fetchall()
    seen = hosts(executor.log)
    charged = sum(row[5] or 0 for row in invocations)
    open_reservations = sum(row[4] for row in invocations if row[3] not in ("succeeded",))
    report = {
        "schema_version": "autobots.browse-trial/v1",
        "completed_at_utc": datetime.now(UTC).isoformat(),
        "evidence_class": "live" if make_client is None else "fake_transport",
        "run_id": str(run),
        "route": {"role": route.role, "profile": route.profile, "wire_id": route.wire_id},
        "worst_case_micro_usd_per_call": route.worst_case_micro_usd,
        "limit_micro_usd": LIMIT_MICRO_USD,
        "charged_micro_usd": charged,
        "open_reservations_micro_usd": open_reservations,
        "within_limit": charged + open_reservations <= LIMIT_MICRO_USD,
        "outcome": result.outcome.value,
        "code": result.code,
        "output": result.output,
        "invocations": [
            dict(
                zip(
                    (
                        "role",
                        "profile",
                        "wire_id",
                        "status",
                        "reserved_micro_usd",
                        "charged_micro_usd",
                        "finish_reason",
                        "input_tokens",
                        "output_tokens",
                        "tool_names",
                        "upstream_provider",
                    ),
                    row,
                    strict=True,
                )
            )
            for row in invocations
        ],
        "tool_uses": [
            dict(
                zip(
                    ("outcome", "code", "metered", "input_public", "output_public"),
                    row,
                    strict=True,
                )
            )
            for row in uses
        ],
        "proxy_hosts": seen,
        "only_allowed_hosts": all(inside(host) for host in seen["connected"]),
        "not_established": ["H1", "product acceptance", "that browsing is reliable"],
    }
    _write(out, report)
    return report


async def _main(arguments: argparse.Namespace) -> int:
    forbid_remote_tracing(os.environ)
    configure_logging()
    out = Path(arguments.out)
    try:
        refuse_repeat(out, arguments.owner_requested_repeat)
        key = read_key(Path(arguments.key_file))
        payload = await catalog_fetcher()()
        if payload is None:
            raise Refused("the catalog couldn't be read, so nothing was sent")
        report = await run_trial(
            os.environ["AUTOBOTS_DATABASE_URL"], UUID(arguments.workspace), key, out, payload
        )
    except Refused as refusal:
        print(f"REFUSED: {refusal}", file=sys.stderr)
        return 1
    summary = {
        name: report[name]
        for name in ("outcome", "code", "charged_micro_usd", "within_limit", "only_allowed_hosts")
    }
    summary["stopped"] = (report["output"] or {}).get("stopped")
    summary["calls"] = len(report["invocations"])
    summary["hosts"] = report["proxy_hosts"]["connected"]
    print(json.dumps(summary))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key-file", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--owner-requested-repeat", action="store_true")
    return asyncio.run(_main(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
