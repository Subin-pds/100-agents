"""Research tools for the LangGraph implementation.

Same logic as crewai/tools.py, wrapped with LangChain's @tool instead of
CrewAI's. Kept as a separate copy on purpose: each framework folder stays
self-contained, so the two implementations can be read and run independently.
"""

import httpx
import lxml.html
from ddgs import DDGS
from langchain_core.tools import tool

# Every page read is re-sent on each later loop step, so page size multiplies cost.
MAX_PAGE_CHARS = 3000


def _format_results(results: list[dict], date_key: str | None = None) -> str:
    if not results:
        return "No results found. Try a broader or differently worded query."
    lines = []
    for i, r in enumerate(results, 1):
        date = f" ({r.get(date_key, '')[:10]})" if date_key else ""
        url = r.get("href") or r.get("url", "")
        lines.append(f"{i}. {r.get('title', '')}{date}\n   {url}\n   {r.get('body', '')}")
    return "\n\n".join(lines)


# LangChain builds the tool schema from the function name, type hints and
# docstring — the docstring is what the LLM reads to decide when to call it.
@tool
def web_search(query: str) -> str:
    """Search the web and return the top 8 results (title, URL, snippet).
    Use for evergreen questions: framework comparisons, certification details,
    skill requirements, salary ranges."""
    try:
        with DDGS() as ddgs:
            return _format_results(list(ddgs.text(query, max_results=8)))
    except Exception as exc:
        # Returned as text so the agent can rephrase instead of the graph crashing.
        return f"Search failed: {exc}"


@tool
def news_search(query: str) -> str:
    """Search news from the past month and return up to 8 dated articles.
    Use for anything time-sensitive: new model or tool launches, funding,
    hiring announcements, layoffs."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.news(query, max_results=8, timelimit="m"))
        return _format_results(results, date_key="date")
    except Exception as exc:
        return f"News search failed: {exc}"


@tool
def fetch_page(url: str) -> str:
    """Download a web page and return its main readable text (truncated).
    Use after a search when a snippet is too thin and you need the details."""
    try:
        resp = httpx.get(
            url,
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (career-research-graph)"},
        )
        resp.raise_for_status()
    except Exception as exc:
        return f"Could not fetch {url}: {exc}"

    doc = lxml.html.fromstring(resp.text)
    for bad in doc.xpath("//script|//style|//nav|//footer|//header|//noscript"):
        bad.drop_tree()
    text = " ".join(doc.text_content().split())
    return text[:MAX_PAGE_CHARS] or "Page had no readable text."


RESEARCH_TOOLS = [web_search, news_search, fetch_page]
