"""Tool registry and implementations for Agent 1.

CCA-F Domain 2 — Tool Design & MCP Integration:
    A tool has four parts: name, description, input schema, and implementation.
    The LLM never sees the implementation — only name + description + schema.
    This is the contract between the orchestrator and the outside world.
"""

# INTERVIEW: Why is tool description wording critical? The LLM decides which
# tool to call by reading the description. Vague descriptions = wrong tool
# selection. Precise descriptions = reliable agents.

import ast
import datetime
import json
import urllib.parse
import urllib.request


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def search_web(query: str) -> str:
    """Search the web via DuckDuckGo Instant Answer API and return a text summary.

    CCA-F Domain 2 — Tool Design:
        Tools must handle their own exceptions and return strings. The agent
        loop is not responsible for catching tool errors — the tool is. This
        keeps the core loop clean and predictable.
    """
    # INTERVIEW: Why DuckDuckGo? No API key required — zero friction for a
    # portfolio demo. In production you'd use SerpAPI or Brave Search API.
    encoded = urllib.parse.quote_plus(query)
    url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception as exc:
        return f"Search error: {exc}"

    if data.get("AbstractText"):
        return data["AbstractText"]
    if data.get("Answer"):
        return data["Answer"]
    related = data.get("RelatedTopics", [])
    snippets = []
    for item in related[:3]:
        if isinstance(item, dict) and item.get("Text"):
            snippets.append(item["Text"])
    if snippets:
        return "\n".join(snippets)
    return "No result found for that query."


def calculate(expression: str) -> str:
    """Safely evaluate a mathematical expression and return the result as a string.

    CCA-F Domain 2 — Tool Design:
        Security matters in tool design. Never use raw eval() on LLM-generated
        strings — the LLM could produce expressions like __import__('os').system('rm -rf /').
        AST whitelisting allows math while blocking all other Python operations.
    """
    # INTERVIEW: Why AST-safe eval instead of raw eval()? eval() on untrusted
    # strings is Remote Code Execution (RCE). We walk the AST and whitelist
    # only arithmetic node types — the LLM gets math, not shell access.
    SAFE_NODES = {
        ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow,
        ast.Mod, ast.FloorDiv, ast.USub, ast.UAdd,
    }
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as exc:
        return f"Syntax error in expression: {exc}"

    for node in ast.walk(tree):
        if type(node) not in SAFE_NODES:
            return f"Unsafe operation '{type(node).__name__}' not allowed."

    try:
        result = eval(compile(tree, "<expr>", "eval"))  # noqa: S307
        return str(result)
    except Exception as exc:
        return f"Calculation error: {exc}"


def get_current_date() -> str:
    """Return today's date in ISO 8601 format.

    CCA-F Domain 2 — Tool Design:
        Even trivial tools have value. LLMs have a training cutoff — they do
        not know today's date. This tool grounds the agent in real time.
    """
    # INTERVIEW: Why does the LLM need a tool for the current date? Its
    # knowledge has a training cutoff. Without this tool, it would guess or
    # hallucinate the date. Tools inject real-world grounding.
    return datetime.date.today().isoformat()


# ---------------------------------------------------------------------------
# Registry
# CCA-F Domain 2: The registry decouples tool lookup from tool implementation.
# The agent loop calls execute_tool(name, input) — it never imports tools directly.
# ---------------------------------------------------------------------------

TOOLS: dict[str, callable] = {
    "search_web": search_web,
    "calculate": calculate,
    "get_current_date": get_current_date,
}

# INTERVIEW: TOOL_SCHEMAS are JSON Schema objects sent to the Anthropic API.
# The LLM reads name + description to choose a tool, and input_schema to know
# what arguments to produce. The implementation is invisible to the model.
TOOL_SCHEMAS: list[dict] = [
    {
        "name": "search_web",
        "description": "Search the web for current information on a topic.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "calculate",
        "description": "Evaluate a safe mathematical expression (e.g. '15 / 100 * 3400000').",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "A Python-compatible math expression.",
                },
            },
            "required": ["expression"],
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
    """Look up a tool by name and call it with the given input dict.

    CCA-F Domain 2 — Tool Execution:
        This is the boundary between the agent loop and the outside world.
        All exceptions are caught here — the loop receives a string result
        whether the tool succeeds or fails. Never let a tool crash the loop.
    """
    # INTERVIEW: Why catch exceptions here and not in the loop? The agent loop
    # should be agnostic to what tools do. Returning an error string lets the
    # LLM read the error and decide whether to retry or change approach.
    if name not in TOOLS:
        return f"Unknown tool: {name}"
    try:
        return TOOLS[name](**tool_input)
    except Exception as exc:
        return f"Tool '{name}' raised an error: {exc}"
