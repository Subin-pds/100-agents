"""CLI entry point for Agent 5 — LangGraph Research Agent.

Usage:
    python main.py "topic to research"
"""

import sys
import uuid

from dotenv import load_dotenv

# Windows terminals default to cp1252, which can't encode emoji that show up
# in LangChain's pretty-printed messages — force UTF-8 stdout instead.
sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

from agent.graph import build_graph  # noqa: E402  (import after load_dotenv)


def run(topic: str) -> str:
    graph = build_graph()
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    final_message = None
    for event in graph.stream(
        {"messages": [("user", f"Research topic: {topic}")]},
        config=config,
        stream_mode="values",
    ):
        final_message = event["messages"][-1]
        final_message.pretty_print()
    return final_message.content if final_message else ""


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python main.py "topic"')
        sys.exit(1)
    run(sys.argv[1])
