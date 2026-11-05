"""A real LangGraph graph with no model. Each node's effect is a line in a file outside the database."""
from __future__ import annotations

import operator
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph


class State(TypedDict):
    seen: Annotated[list[str], operator.add]


def build(saver: Any, log: str, before_finish: Callable[[str], None] = lambda _: None) -> Any:
    def node(name: str) -> Callable[[State], dict[str, list[str]]]:
        def run(_: State) -> dict[str, list[str]]:
            with Path(log).open('a') as handle:
                handle.write(f'{name}\n')
            before_finish(name)
            return {'seen': [name]}
        return run

    graph = StateGraph(State)
    for name in ('first', 'second', 'third'):
        graph.add_node(name, node(name))
    graph.add_edge(START, 'first')
    graph.add_edge('first', 'second')
    graph.add_edge('second', 'third')
    graph.add_edge('third', END)
    return graph.compile(checkpointer=saver)
