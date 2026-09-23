"""One local LangGraph routes typed plans; no finance or provider bootstrap."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, TypedDict

from langgraph.graph import END, START, StateGraph


class ConversationState(TypedDict, total=False):
    plan: dict[str, Any]
    final: dict[str, Any]


async def run_conversation_graph(
    plan: Callable[[], Awaitable[dict]],
    handlers: dict[str, Callable[[dict], Awaitable[dict]]],
) -> dict:
    async def interpret_node(state: ConversationState):
        return {"plan": await plan()}

    def execute_node(kind):
        async def execute(state: ConversationState):
            return {"final": await handlers[kind](state["plan"])}

        return execute

    graph = StateGraph(ConversationState)
    graph.add_node("interpret", interpret_node)
    graph.add_edge(START, "interpret")
    for kind in handlers:
        graph.add_node(kind, execute_node(kind))
        graph.add_edge(kind, END)
    graph.add_conditional_edges(
        "interpret",
        lambda state: state["plan"]["kind"],
        {kind: kind for kind in handlers},
    )
    return (await graph.compile().ainvoke({}))["final"]
