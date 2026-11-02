"""
This is a coding practice for the langraph agent step_1_hello_graph.py
"""

import sys
from dotenv import load_dotenv
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import START, END, StateGraph
from typing import TypedDict

from llm_copy import make_llm

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

llm = make_llm("LLM_MODEL")

SYSTEM_PROMPT = (
    "You are a career coach who has placed dozens of AI engineers into Google, Amazon "
    "and Meta. Give sharp, specific advice to engineers targeting MAANG AI roles."
)

class State(TypedDict):
    question : str
    answer : str
    usage : dict

def coach(state:State) -> dict:
    response = llm.invoke(
        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=state['question'])]
    )
    return {'answer': response.text, 'usage' : response.usage_metadata or {}}


builder = StateGraph(State)
builder.add_node("coach", coach)
builder.add_edge(START,"coach")
builder.add_edge("coach", END)
app = builder.compile()


if __name__ == "__main__":
    print('App structure, Mermaid')
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
    print("="*60)
    print(result['answer'])
    print("="*60)
    print(f'Token usage : {result['usage']}')