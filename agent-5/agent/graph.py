"""LangGraph StateGraph for Agent 5 — Research Agent.

Same idea as Agent 4's hand-written ReAct loop (search the web, synthesise,
report back) but expressed as an explicit graph: nodes, edges, and a
conditional branch instead of a for-loop with if/else on stop_reason.
"""

from typing import Annotated, TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from .tools import TOOLS

SYSTEM_PROMPT = """\
You are a Research Agent. Given a topic:
1. Break it into 2-4 focused search queries covering different angles.
2. Call web_search for each query, one at a time.
3. Once you have enough information, synthesise it into a structured report:

## Summary
{2-3 paragraphs synthesising findings}

## Key Findings
- {finding}
- {finding}

## Sources Consulted
- {queries you ran}

Never fabricate facts — only report what the searches returned.
"""


class State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def build_graph():
    """Compile the research graph. Call once per process; reuse the result."""
    llm = ChatAnthropic(model="claude-sonnet-4-5", temperature=0).bind_tools(TOOLS)

    def agent_node(state: State) -> dict:
        messages = state["messages"]
        if not any(isinstance(m, SystemMessage) for m in messages):
            messages = [SystemMessage(content=SYSTEM_PROMPT), *messages]
        return {"messages": [llm.invoke(messages)]}

    graph = StateGraph(State)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(TOOLS))
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")
    return graph.compile(checkpointer=MemorySaver())
