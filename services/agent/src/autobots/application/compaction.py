"""Context stays bounded, and what must not be lost stays out of anything lossy, PRD 8.4.

The goal, criteria, permissions and open waits come from the database on every compacted call, never
from a summary. Long tool output moves out whole and stays readable. Only the model's view of the
conversation changes here: the checkpointed conversation keeps every message.
"""

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from autobots.contracts.plans import GoalSpec

LARGE_TOOL_CHARS = 4_000
PREVIEW_CHARS = 300
READ_BACK_TOOL = "read_offload"
READ_PAGES_IN_VIEW = 2
KEEP_RECENT = 6
SUMMARY_MARKER = "Summarize the earlier work below"


@dataclass(frozen=True)
class CompactionPolicy:
    """A rough character budget, since no tokenizer is pinned. 8K tokens is about 32K characters."""

    context_chars: int = 24_000
    large_tool_chars: int = LARGE_TOOL_CHARS
    keep_recent: int = KEEP_RECENT


@dataclass(frozen=True)
class StoredSummary:
    covers: int
    summary: str
    sources: tuple[str, ...]


def _text(message: Any) -> str:
    content = message.content
    calls = getattr(message, "tool_calls", None) or []
    return (content if isinstance(content, str) else json.dumps(content, default=str)) + json.dumps(
        [call.get("args") for call in calls], default=str
    )


def total_chars(messages: Sequence[Any]) -> int:
    return sum(len(_text(message)) for message in messages)


async def offload_large(
    connection: Any, run_id: UUID, messages: Sequence[Any], policy: CompactionPolicy
) -> list[Any]:
    """Keeps a pointer and a short preview. The same call always maps to the same stored row."""
    view: list[Any] = []
    pages = [m for m in messages if m.type == "tool" and m.name == READ_BACK_TOOL]
    kept_pages = {id(m) for m in pages[-READ_PAGES_IN_VIEW:]}
    for message in messages:
        content = message.content
        if message.type != "tool" or not isinstance(content, str):
            view.append(message)
            continue
        if message.name == READ_BACK_TOOL:
            # A bounded page of stored evidence. Offloading it again could never end, and only the
            # latest stay in view, as a long read would otherwise resend every page on every call.
            if id(message) in kept_pages:
                view.append(message)
            else:
                stub = json.dumps({"page_dropped": "Read it again with read_offload if needed."})
                view.append(message.model_copy(update={"content": stub}))
            continue
        if len(content) <= policy.large_tool_chars:
            view.append(message)
            continue
        digest = hashlib.sha256(content.encode()).hexdigest()
        await connection.execute(
            "insert into app_private.run_offloads (id, run_id, tool_call_id, tool_name, content, "
            "sha256) values (%s, %s, %s, %s, %s, %s) on conflict (run_id, tool_call_id) do nothing",
            (uuid4(), run_id, message.tool_call_id, message.name or "", content, digest),
        )
        cursor = await connection.execute(
            "select id from app_private.run_offloads where run_id = %s and tool_call_id = %s",
            (run_id, message.tool_call_id),
        )
        offload_id = (await cursor.fetchone())[0]
        pointer = json.dumps(
            {
                "offloaded": str(offload_id),
                "tool": message.name,
                "characters": len(content),
                "preview": content[:PREVIEW_CHARS],
                "read_with": "read_offload",
            }
        )
        view.append(message.model_copy(update={"content": pointer}))
    return view


def safe_split(messages: Sequence[Any], keep_recent: int) -> int:
    """Where to cut, never between a tool call and its results. Returns how many are summarized."""
    cut = max(0, len(messages) - keep_recent)
    while cut > 0 and messages[cut].type == "tool":
        cut -= 1
    return cut


def pairing_is_valid(messages: Sequence[Any]) -> bool:
    """Every result has its call, and every call before the end has its results."""
    open_calls: set[str] = set()
    for message in messages:
        if message.type == "tool":
            if message.tool_call_id not in open_calls:
                return False
            open_calls.discard(message.tool_call_id)
            continue
        if open_calls:
            return False
        open_calls |= {call["id"] for call in getattr(message, "tool_calls", None) or []}
    return True


async def state_block(connection: Any, run_id: UUID, goal: GoalSpec) -> str:
    """Read fresh, so a summary can't lose or change any of this."""
    cursor = await connection.execute(
        "select kind, detail from app_private.run_obligations "
        "where run_id = %s and status = 'open' order by created_at",
        (run_id,),
    )
    obligations = await cursor.fetchall()
    cursor = await connection.execute(
        "select tool_id from public.approval_requests "
        "where run_id = %s and status = 'pending' order by created_at",
        (run_id,),
    )
    approvals = [row[0] for row in await cursor.fetchall()]
    criteria = "\n".join(f"- {name}: {text}" for name, text in sorted(goal.criteria.items()))
    lines = [
        "Current state, from the run's records. This is authoritative over any summary.",
        f"Goal: {goal.objective}",
        f"Criteria:\n{criteria}",
        f"Allowed tools: {', '.join(sorted(goal.allowed_tools))}",
        f"Allowed paths: {', '.join(goal.allowed_paths)}",
    ]
    if obligations:
        lines.append(
            "Open waits: " + "; ".join(f"{kind}: {detail}" for kind, detail in obligations)
        )
    if approvals:
        lines.append("Pending approvals: " + ", ".join(approvals))
    return "\n".join(lines)


def _offload_ids(messages: Sequence[Any]) -> list[str]:
    found = []
    for message in messages:
        if message.type != "tool":
            continue
        try:
            pointer = json.loads(message.content)
        except (TypeError, ValueError):
            continue
        if isinstance(pointer, dict) and "offloaded" in pointer:
            found.append(str(pointer["offloaded"]))
    return found


def summary_request(earlier: Sequence[Any], previous: StoredSummary | None) -> str:
    parts = [f"{SUMMARY_MARKER}, briefly. Say what was done and found, not what to do."]
    if previous is not None:
        parts.append(f"Earlier summary:\n{previous.summary}")
    parts.extend(f"{message.type}: {_text(message)[:2000]}" for message in earlier)
    return "\n\n".join(parts)


async def latest_summary(connection: Any, run_id: UUID) -> StoredSummary | None:
    cursor = await connection.execute(
        "select covers, summary, sources from app_private.run_summaries "
        "where run_id = %s order by covers desc limit 1",
        (run_id,),
    )
    row = await cursor.fetchone()
    return StoredSummary(row[0], row[1], tuple(row[2])) if row else None


async def store_summary(
    connection: Any,
    run_id: UUID,
    covers: int,
    summary: str,
    earlier: Sequence[Any],
    previous: StoredSummary | None,
    role: str,
    profile: str,
) -> StoredSummary:
    """Sources are worked out here, so a citation can't be something a model made up."""
    sources = tuple(
        dict.fromkeys([*(previous.sources if previous else ()), *_offload_ids(earlier)])
    )
    await connection.execute(
        "insert into app_private.run_summaries (id, run_id, covers, summary, sources, role, "
        "profile) values (%s, %s, %s, %s, %s, %s, %s)",
        (uuid4(), run_id, covers, summary, json.dumps(sources), role, profile),
    )
    return StoredSummary(covers, summary, sources)


def summary_text(stored: StoredSummary) -> str:
    cited = (
        "\nStored results you can read with read_offload: " + ", ".join(stored.sources)
        if stored.sources
        else ""
    )
    return f"Summary of earlier work. It may be incomplete.\n{stored.summary}{cited}"
