"""Tool registry for Agent 4 — Research Summariser.

CCA-F Domain 2 — Tool Design & MCP Integration:
    This file demonstrates two tool categories:
    1. Read tools — search_web, get_current_date (fetch information)
    2. Write tools — save_to_obsidian (produce a side effect)
    Both must handle exceptions internally and return strings.
    The agent loop is never responsible for catching tool errors.
"""

# INTERVIEW: What are the two categories of agent tools?
# Read tools: fetch information (search, API calls, calculations)
# Write tools: produce side effects (save files, send emails, update DBs)
# Both categories must return strings and handle their own exceptions.

import datetime
import json
import pathlib
import urllib.parse
import urllib.request

# CCA-F Domain 2: The vault path is a configuration constant, not hardcoded
# throughout the code. One place to change if the vault moves.
OBSIDIAN_VAULT = pathlib.Path(r"C:\Users\subin\obsidianvault")
RESEARCH_NOTES_FOLDER = OBSIDIAN_VAULT / "Research" / "Agent4"


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def search_web(query: str) -> str:
    """Search the web via DuckDuckGo Instant Answer API and return results.

    CCA-F Domain 2 — Tool Design:
        Tools must be self-contained. They handle their own network errors,
        parse responses, and return a clean string the LLM can read.
        The agent loop calls execute_tool() — it never imports this directly.
    """
    # INTERVIEW: Why DuckDuckGo? Zero API key requirement — perfect for demos.
    # Production alternatives: Brave Search API, Tavily, SerpAPI (richer results).
    # Trade-off: DDG Instant Answer API is limited but requires no credentials.
    encoded = urllib.parse.quote_plus(query)
    url = (
        f"https://api.duckduckgo.com/?q={encoded}"
        f"&format=json&no_html=1&skip_disambig=1"
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception as exc:
        return f"Search error: {exc}"

    parts: list[str] = []
    if data.get("AbstractText"):
        parts.append(data["AbstractText"])
    if data.get("Answer"):
        parts.append(f"Quick answer: {data['Answer']}")
    for item in data.get("RelatedTopics", [])[:4]:
        if isinstance(item, dict) and item.get("Text"):
            parts.append(item["Text"])
    return "\n".join(parts) if parts else "No result found for that query."


def save_to_obsidian(title: str, content: str) -> str:
    """Write a Markdown note to the Obsidian vault and return the file path.

    CCA-F Domain 2 — Write Tool Design:
        Write tools produce side effects — they change state outside the agent.
        Key properties to consider:
        - Idempotency: calling twice with same inputs → same result (this tool
          overwrites, which is intentional — re-runs should update, not duplicate).
        - Atomicity: write is a single operation — no partial writes.
        - Error surfacing: exceptions become readable strings for the LLM.

    INTERVIEW: What is idempotency and why does it matter for agent tools?
        An idempotent operation produces the same result whether called once or
        many times. In agents, tools may be retried on network errors — idempotent
        tools are safe to retry, non-idempotent ones (e.g., send email) are not.
        Design write tools to be idempotent where possible.
    """
    # CCA-F Domain 2: Create the notes folder if absent — the tool is
    # self-bootstrapping, no manual setup required.
    RESEARCH_NOTES_FOLDER.mkdir(parents=True, exist_ok=True)

    # Sanitise title to a safe filename — spaces become underscores,
    # special characters are removed.
    safe = "".join(c if c.isalnum() or c in " -_" else "" for c in title).strip()
    safe = safe.replace(" ", "_")[:80]
    filepath = RESEARCH_NOTES_FOLDER / f"{safe}.md"

    try:
        filepath.write_text(content, encoding="utf-8")
        return f"Saved: {filepath}"
    except Exception as exc:
        return f"Failed to save note: {exc}"


def get_current_date() -> str:
    """Return today's date in ISO 8601 format (YYYY-MM-DD).

    CCA-F Domain 2 — Tool Design:
        Even trivial tools have value. LLMs have a training cutoff — they cannot
        know today's date without a tool. This is called 'grounding': anchoring
        the LLM's reasoning in real-world facts via tools.

    INTERVIEW: Why does an LLM need a tool to get today's date?
        LLMs are trained on static datasets with a knowledge cutoff. They have
        no access to real-time state. Tools inject that real-world grounding.
        This is a fundamental asymmetry: LLMs are good at reasoning, tools
        are good at accessing current reality.
    """
    return datetime.date.today().isoformat()


# ---------------------------------------------------------------------------
# Tool registry
# CCA-F Domain 2: The registry is a dict mapping name → function.
# The agent loop calls execute_tool(name, input) — it never imports tools
# directly. This decouples the loop from tool implementations.
# INTERVIEW: What is the registry pattern? A lookup table that maps string
# names to callables. It enables dynamic dispatch without if/elif chains
# and makes adding new tools a one-line change.
# ---------------------------------------------------------------------------

TOOLS: dict[str, callable] = {
    "search_web": search_web,
    "save_to_obsidian": save_to_obsidian,
    "get_current_date": get_current_date,
}

# CCA-F Domain 2: TOOL_SCHEMAS are JSON Schema objects sent to the API.
# The LLM reads name + description to choose a tool, and input_schema to
# know what arguments to produce. The Python implementation is invisible.
# INTERVIEW: What does the LLM receive when you define a tool?
# Only: name, description, input_schema. Never the implementation code.
# This is the tool contract — the interface between LLM and the real world.
TOOL_SCHEMAS: list[dict] = [
    {
        "name": "search_web",
        "description": (
            "Search the web for information on a query. Returns a text summary "
            "from DuckDuckGo. Use focused, specific queries for best results. "
            "Call multiple times with different queries to cover all angles."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A specific, focused search query.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "save_to_obsidian",
        "description": (
            "Save a Markdown research note to the Obsidian vault. "
            "Call this ONCE after all searches are complete, with the full "
            "structured note as content. Returns the file path on success."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Note title (used as filename). Keep it concise.",
                },
                "content": {
                    "type": "string",
                    "description": "Full Markdown content of the research note.",
                },
            },
            "required": ["title", "content"],
        },
    },
    {
        "name": "get_current_date",
        "description": "Return today's date in YYYY-MM-DD format.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


def execute_tool(name: str, tool_input: dict) -> str:
    """Dispatch a tool call by name and return the result as a string.

    CCA-F Domain 2 — Tool Execution Boundary:
        This is the single entry point from the agent loop to the tool layer.
        All exceptions are caught here — the loop always receives a string,
        whether the tool succeeds or fails. This keeps the loop clean and lets
        the LLM read the error and decide whether to retry or change approach.

    INTERVIEW: Why catch all exceptions at the execution boundary?
        The agent loop should be agnostic to tool internals. If a tool raises,
        returning an error string lets the LLM adapt — it might try a different
        query, use a different tool, or gracefully report the issue. Crashing
        the loop on a tool error wastes all prior computation.
    """
    # CCA-F Domain 2: Unknown tool names surface as errors, not KeyErrors.
    if name not in TOOLS:
        return f"Unknown tool: '{name}'. Available: {list(TOOLS.keys())}"
    try:
        return str(TOOLS[name](**tool_input))
    except Exception as exc:
        return f"Tool '{name}' raised: {exc}"
