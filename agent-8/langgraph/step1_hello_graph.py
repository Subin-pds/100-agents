"""Step 1 (LangGraph) — the smallest possible graph: one node between START and END.

Same job as crewai/step1_hello_crew.py, so the two can be compared line by line:

    CrewAI                          LangGraph
    ------                          ---------
    Agent(role, goal, backstory) -> you write the system prompt yourself
    Task(description)            -> a field in the graph's State
    Crew(agents, tasks)          -> StateGraph + nodes + edges
    crew.kickoff(inputs)         -> app.invoke(initial_state)

    START ──> coach ──> END

Run (from the agent-8 folder):
    venv\\Scripts\\python langgraph\\step1_hello_graph.py
"""

import sys
from typing import TypedDict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from llm import make_llm

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

llm = make_llm("LLM_MODEL")

SYSTEM_PROMPT = (
    "You are a career coach who has placed dozens of AI engineers into Google, Amazon "
    "and Meta. Give sharp, specific advice to engineers targeting MAANG AI roles."
)


# State is the single object that flows through the graph. Every node reads it
# and returns a dict of the fields it wants to update — nothing else is shared.
class State(TypedDict):
    question: str
    answer: str
    usage: dict


def coach(state: State) -> dict:
    """A node is a plain Python function: State in, partial State update out."""
    response = llm.invoke(
        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=state["question"])]
    )
    return {"answer": response.text, "usage": response.usage_metadata or {}}


# Wiring is explicit: you declare every node and every edge. CrewAI inferred
# this from the order of the tasks list; here nothing runs unless an edge says so.
builder = StateGraph(State)
builder.add_node("coach", coach)
builder.add_edge(START, "coach")
builder.add_edge("coach", END)
app = builder.compile()

if __name__ == "__main__":
    print("Graph structure (Mermaid):")
    print(app.get_graph().draw_mermaid())

    result = app.invoke(
        {
            "question": (
                "A mid-level GenAI engineer in India wants to join a MAANG company within "
                "12 months. List the top 5 skills MAANG AI interviews screen for in 2026, "
                "one sentence each."
            )
        }
    )
    print("=" * 60)
    print(result["answer"])
    print("=" * 60)
    print(f"Token usage: {result['usage']}")
