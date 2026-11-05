"""A scripted chat model and the calls the goal loop checks replay. No provider is involved."""
from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import SecretStr

from autobots.adapters.loop_middleware import ModelRoute

ROUTE = ModelRoute('executor', 'openrouter_deepseek_flash', 'fixture/model', 1000)
_ids = iter(range(1, 100000))


class Script(BaseChatModel):
    items: list[Any]
    # Held the way a real client holds a key, to show it stays out of checkpoints.
    api_key: SecretStr = SecretStr('sk-or-planted-secret-value')
    seen: list[list[Any]] = []
    bound: list[list[str]] = []

    @property
    def _llm_type(self) -> str:
        return 'script'

    def bind_tools(self, tools: Any, **_: Any) -> Any:
        self.bound.append([getattr(tool, 'name', str(tool)) for tool in tools])
        return self

    def _generate(self, messages: Any, stop: Any = None, run_manager: Any = None, **_: Any) -> ChatResult:
        self.seen.append(list(messages))
        item = self.items.pop(0) if self.items else say('the script ran out')
        if isinstance(item, BaseException):
            raise item
        if callable(item):
            item = item()
        return ChatResult(generations=[ChatGeneration(message=item)])


def calls(*pairs: tuple[str, dict[str, Any]], finish: str = 'tool_calls', cost: float | None = 0.0001) -> AIMessage:
    metadata: dict[str, Any] = {'finish_reason': finish}
    if cost is not None:
        metadata['cost'] = cost
    return AIMessage(content='', response_metadata=metadata, tool_calls=[{'name': n, 'args': a, 'id': f'call-{next(_ids)}', 'type': 'tool_call'} for n, a in pairs])


def say(text: str, finish: str = 'stop', cost: float | None = 0.0001) -> AIMessage:
    metadata: dict[str, Any] = {'finish_reason': finish}
    if cost is not None:
        metadata['cost'] = cost
    return AIMessage(content=text, response_metadata=metadata)


TASK_A = {'id': 'a', 'title': 'Summary', 'criteria': ['c1'], 'expected_evidence': 'a file'}
TASK_B = {'id': 'b', 'title': 'Figures', 'criteria': ['c2'], 'expected_evidence': 'a file', 'depends_on': ['a']}
PLAN = ('propose_plan', {'tasks': [TASK_A, TASK_B]})
SAVE = ('save_artifact', {'path': 'outputs/a.md', 'content': 'summary'})
DONE_A = ('complete_task', {'task_id': 'a', 'evidence': [{'kind': 'artifact', 'reference': 'outputs/a.md'}], 'summary': 'wrote it'})
