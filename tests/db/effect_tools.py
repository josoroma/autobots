"""Consequential tools over the controlled sink, one that can read back and one that can't."""
from __future__ import annotations

import os
import signal
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

sys.path.insert(0, str(Path(__file__).parent))
from autobots.application.tool_gateway import NotDelivered, ToolContext, ToolDefinition, ToolFailed
from autobots.domain.tools import OperationClass
from mock_sink import Sink


class SendInput(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)

    body: str


class SendOutput(BaseModel):
    model_config = ConfigDict(extra='allow', frozen=True)

    delivered: bool = True


def tools(sink: Sink, *, behavior: dict[str, str] | None = None) -> tuple[ToolDefinition, ToolDefinition]:
    """`behavior` maps a body to what the send does: lose_ack, die_after, or refuse."""
    plan = behavior or {}

    async def send(arguments: SendInput, context: ToolContext) -> SendOutput:
        mode = plan.get(arguments.body, '')
        if mode == 'refuse':
            raise ToolFailed('destination_refused')
        sink.deliver(str(context.operation_id), arguments.body)
        if mode == 'lose_ack':
            raise ConnectionError('the acknowledgment never arrived')
        if mode == 'die_after':
            os.kill(os.getpid(), signal.SIGKILL)
        return SendOutput()

    async def readback(_: SendInput, context: ToolContext) -> Any:
        if sink.holds(str(context.operation_id)):
            return SendOutput()
        raise NotDelivered

    readable = ToolDefinition(tool_id='send_readable', version=1, description='Send, with readback.', input_model=SendInput, output_model=SendOutput, operation_class=OperationClass.CONSEQUENTIAL_EXTERNAL_WRITE, handler=send, reconcile=readback)
    blind = ToolDefinition(tool_id='send_blind', version=1, description='Send, with no readback.', input_model=SendInput, output_model=SendOutput, operation_class=OperationClass.CONSEQUENTIAL_EXTERNAL_WRITE, handler=send)
    return readable, blind
