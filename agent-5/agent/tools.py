"""Tools for Agent 5 — LangGraph Research Agent."""

from ddgs import DDGS
from langchain_core.tools import tool


@tool
def web_search(query: str) -> str:
    """Search the web for information on a query and return a text summary.

    Use a focused, specific query. Call this multiple times with different
    queries to cover different angles of a topic.
    """
    try:
        results = list(DDGS().text(query, max_results=5))
    except Exception as exc:
        return f"Search error: {exc}"

    if not results:
        return "No result found for that query."

    return "\n\n".join(
        f"{r['title']}\n{r['body']}\n{r['href']}" for r in results
    )


TOOLS = [web_search]
