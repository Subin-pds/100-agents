"""Step 2 (LangGraph) — one agent with tools: the AI Trends Researcher.

Same job as crewai/step2_trends_researcher.py. In CrewAI the tool loop was
hidden inside the Agent; here you build it yourself as a graph:

                   ┌──────────── tools ◀───┐
                   ▼                       │ (tool calls, budget left)
    START ──▶ researcher ──── route ───────┤
                                           ├──▶ finalize ──▶ END   (budget used up, or empty reply)
                                           └──▶ END                (final answer)

New concepts vs step 1:
  - messages state with the add_messages reducer (append, don't overwrite)
  - ToolNode: runs whatever tool calls the model asked for
  - a conditional edge (the router) and a loop back to an earlier node
  - a tool budget enforced in code, not just requested in the prompt
  - app.stream(): watch each node as it runs
  - LangSmith tracing, switched on purely by environment variables

Run (from the agent-8 folder):
    venv\\Scripts\\python langgraph\\step2_trends_researcher.py
"""

import datetime
import os
import pathlib
import sys
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from llm import make_llm
from tools import RESEARCH_TOOLS

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# Hard cap on tool calls. In CrewAI this budget was only a sentence in the task
# ("at most 5 searches") that the model could ignore; here the router enforces it.
MAX_TOOL_CALLS = 7

REPORT_PATH = pathlib.Path(__file__).parent / "reports" / "step2_ai_trends.md"

SYSTEM_PROMPT = """\
You are a staff engineer who writes a weekly AI-engineering briefing read by hiring
managers at Google, Meta and Amazon. You only report what you can cite, prefer
primary sources over listicles, and separate durable shifts from hype.

Today is {today}. Research the AI engineering landscape of the last 3 months:
(1) notable new models, (2) agent frameworks and protocols gaining adoption,
(3) developer tools and infra (eval, observability, inference),
(4) AI certifications valued by big-tech hiring,
(5) skills becoming table stakes vs fading.

Use the tools to research, then write the final briefing: one markdown section per
topic, 2-4 bullets each, every bullet with a source URL and date. End with a
'Top 5 durable trends' list, ranked. You have a budget of {budget} tool calls.
"""

llm_with_tools = make_llm("RESEARCH_MODEL", tools=RESEARCH_TOOLS)
llm_plain = make_llm("RESEARCH_MODEL")


class State(TypedDict):
    # add_messages is a reducer: a node returning {"messages": [msg]} APPENDS msg
    # to the history instead of replacing the whole list (the default for a key).
    messages: Annotated[list[AnyMessage], add_messages]
    tool_calls_made: int


def researcher(state: State) -> dict:
    """The LLM step: either asks for tools or writes the final answer."""
    return {"messages": [llm_with_tools.invoke(state["messages"])]}


tool_node = ToolNode(RESEARCH_TOOLS)


def run_tools(state: State) -> dict:
    """Run the requested tools and count them against the budget."""
    result = tool_node.invoke(state)
    return {
        "messages": result["messages"],
        "tool_calls_made": state["tool_calls_made"] + len(result["messages"]),
    }


def finalize(state: State) -> dict:
    """Force a final answer from what has been gathered so far.

    Reached when the tool budget is exhausted, or when the researcher returned
    an empty message instead of an answer.
    """
    # The last AIMessage is either a tool call we won't run (providers reject a
    # tool call with no matching result) or an empty reply — drop it either way.
    history = state["messages"][:-1]
    instruction = HumanMessage(
        content="Stop researching. Write the final briefing now, using only "
        "the information gathered above."
    )
    return {"messages": [llm_plain.invoke(history + [instruction])]}


def route(state: State) -> str:
    """Conditional edge: decide where to go after the researcher speaks."""
    last = state["messages"][-1]
    if not isinstance(last, AIMessage) or not last.tool_calls:
        # No tool calls normally means "final answer" — but Gemini can also return
        # an empty message (finish_reason MALFORMED_FUNCTION_CALL) when it botches a
        # tool call. Treating that as done saved an empty report, so recover via
        # finalize, which uses the tool-less model and cannot make the same mistake.
        if isinstance(last, AIMessage) and not last.text.strip():
            return "finalize"
        return END
    if state["tool_calls_made"] + len(last.tool_calls) > MAX_TOOL_CALLS:
        return "finalize"
    return "tools"


builder = StateGraph(State)
builder.add_node("researcher", researcher)
builder.add_node("tools", run_tools)
builder.add_node("finalize", finalize)
builder.add_edge(START, "researcher")
builder.add_conditional_edges("researcher", route, ["tools", "finalize", END])
builder.add_edge("tools", "researcher")  # the loop: tool results go back to the LLM
builder.add_edge("finalize", END)
app = builder.compile()


def total_usage(messages: list[AnyMessage]) -> dict:
    totals = {"input_tokens": 0, "output_tokens": 0, "llm_calls": 0}
    for m in messages:
        if isinstance(m, AIMessage) and m.usage_metadata:
            totals["input_tokens"] += m.usage_metadata.get("input_tokens", 0)
            totals["output_tokens"] += m.usage_metadata.get("output_tokens", 0)
            totals["llm_calls"] += 1
    return totals


if __name__ == "__main__":
    tracing = os.getenv("LANGSMITH_TRACING", "").lower() == "true" and os.getenv("LANGSMITH_API_KEY")
    print(f"LangSmith tracing: {'ON' if tracing else 'off (set LANGSMITH_TRACING + LANGSMITH_API_KEY to enable)'}")

    initial = {
        "messages": [
            SystemMessage(
                content=SYSTEM_PROMPT.format(
                    today=datetime.date.today().isoformat(), budget=MAX_TOOL_CALLS
                )
            ),
            HumanMessage(content="Write this week's AI engineering briefing."),
        ],
        "tool_calls_made": 0,
    }

    # stream_mode="updates" yields {node_name: update} after every node, so you
    # can watch the loop happen instead of waiting for one final result.
    final_messages = list(initial["messages"])
    for step in app.stream(initial, stream_mode="updates"):
        for node, update in step.items():
            for msg in update.get("messages", []):
                final_messages.append(msg)
                if isinstance(msg, AIMessage) and msg.tool_calls:
                    for call in msg.tool_calls:
                        print(f"[{node}] wants {call['name']}({call['args']})")
                elif isinstance(msg, AIMessage):
                    print(f"[{node}] final answer ({len(msg.text):,} chars)")
                else:
                    print(f"[{node}] {msg.name} returned {len(msg.text):,} chars")

    report = final_messages[-1].text
    if not report.strip():
        # Never overwrite a good report from an earlier run with an empty one.
        reason = final_messages[-1].response_metadata.get("finish_reason")
        sys.exit(f"Final message was empty (finish_reason={reason}); report not saved.")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print("=" * 60)
    print(f"Saved to {REPORT_PATH}")
    print(f"Usage: {total_usage(final_messages)}")
