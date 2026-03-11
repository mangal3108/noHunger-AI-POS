from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypedDict

try:
    from langgraph.graph import END, StateGraph

    HAS_LANGGRAPH = True
except Exception:  # pragma: no cover
    HAS_LANGGRAPH = False


class AgentState(TypedDict):
    session_id: str
    message: str
    response: str


def build_runner(
    handler: Callable[[str, str], Awaitable[str]],
    enabled: bool = False,
) -> Callable[[str, str], Awaitable[str]]:
    if not enabled or not HAS_LANGGRAPH:
        return handler

    try:
        async def agent_node(state: AgentState) -> dict[str, str]:
            response = await handler(state["session_id"], state["message"])
            return {"response": response}

        graph = StateGraph(AgentState)
        graph.add_node("agent", agent_node)
        graph.set_entry_point("agent")
        graph.add_edge("agent", END)
        compiled = graph.compile()

        async def run(session_id: str, message: str) -> str:
            result = await compiled.ainvoke({"session_id": session_id, "message": message, "response": ""})
            return result["response"]

        return run
    except Exception:
        return handler
