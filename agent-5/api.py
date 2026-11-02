"""FastAPI wrapper around the LangGraph research agent.

Run locally:
    uvicorn api:app --reload --port 8080

The graph is built once at process startup and reused across requests;
each request gets its own thread_id so conversations don't bleed into
each other.
"""

import uuid

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

load_dotenv()

from agent.graph import build_graph  # noqa: E402  (import after load_dotenv)

app = FastAPI(title="Agent 5 — Research Agent")
graph = build_graph()


class ResearchRequest(BaseModel):
    topic: str


class ResearchResponse(BaseModel):
    report: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/research", response_model=ResearchResponse)
def research(request: ResearchRequest) -> ResearchResponse:
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    result = graph.invoke(
        {"messages": [("user", f"Research topic: {request.topic}")]},
        config=config,
    )
    return ResearchResponse(report=result["messages"][-1].content)
