"""What the goal loop's model is told: its standing instructions, the goal's opening, and what the
run can reach. A plan cites the listed criterion IDs and nothing else (Decision 0023 E8)."""

from uuid import UUID

from autobots.application.sql import SqlConnection
from autobots.contracts.plans import GoalSpec
from autobots.domain.tools import DELEGATION_TOOL

SYSTEM_PROMPT = (
    "Work only on the stated goal. First call propose_plan, covering every criterion by its ID. "
    "Use only the tools offered. Call complete_task with real evidence as tasks finish. "
    "When every task is complete, reply without calling a tool."
)


async def scope_guidance(connection: SqlConnection, run_id: UUID, goal: GoalSpec) -> str:
    """What this run can reach: where it may write, and which Experts it may assign."""
    lines = [f"You may read and write only under: {', '.join(goal.allowed_paths)}."]
    if DELEGATION_TOOL in goal.allowed_tools:
        cursor = await connection.execute(
            "select e.id, e.name from public.runs r join public.sessions s on s.id = r.session_id "
            "cross join lateral jsonb_array_elements(s.experts) pinned "
            "join public.experts e on e.id = (pinned ->> 'expert_id')::uuid "
            "where r.id = %s order by e.name",
            (run_id,),
        )
        experts = [f"{row[1]} (expert_id {row[0]})" for row in await cursor.fetchall()]
        if experts:
            lines.append(f"With {DELEGATION_TOOL} you may assign work to: {', '.join(experts)}.")
    return "\n".join(lines)


def opening(goal: GoalSpec) -> str:
    """The first message of a goal's pass: its objective, its criteria by ID and, when the run can
    publish, the delivery steps verification looks for."""
    criteria = "\n".join(f"- {name}: {text}" for name, text in sorted(goal.criteria.items()))
    # Decision 0023: a plan cites criteria by ID. A model that copied their text, or treated a
    # delivery step as one, had its plan refused as out of scope, and a refusal names only a code.
    ids = ", ".join(sorted(goal.criteria))
    message = (
        f"Goal: {goal.objective}\n\nCriteria:\n{criteria}\n\n"
        f"In propose_plan, each task's criteria field lists criterion IDs from this list ({ids}) "
        "and nothing else: never their text, and no new criteria."
    )
    if "publish_artifact" not in goal.allowed_tools:
        return message
    # Verification accepts only published files, so the model has to know that from the start.
    lines = [
        "These are steps, not criteria. Saving a file delivers nothing. Before your final "
        "reply, save it under outputs/ with save_artifact, then call publish_artifact with its "
        "path and version."
    ]
    for required in goal.required_artifacts:
        lines.append(f"- Publish a file named {required.name}.")
        lines.extend(f'  It must contain: "{text}"' for text in required.must_contain)
    return f"{message}\n\nDelivery:\n" + "\n".join(lines)
