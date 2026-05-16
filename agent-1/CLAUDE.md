# Agent 1 — Raw Python ReAct Agent

## Project Goal
Build a working ReAct agent in pure Python using only the raw Anthropic API.
Zero frameworks. Zero LangChain. Zero LangGraph. This is the foundation agent
that every subsequent agent in the 100-agent portfolio builds on.

## Who is building this
Subin Sunil Kumar — GenAI Engineer targeting AED 45,000/month UAE role by Aug 2026.
This agent is Week 1 of a 13-week skill sprint. It is also portfolio Agent #1.

### Career Context (read this before writing any code)
- **Target role:** Senior GenAI Engineer in UAE — AED 45,000/month by Aug 10, 2026
- **Active certification:** CCA-F (Claude Certified Architect – Foundations), target Jun 2026
- **Learning philosophy:** Every agent in this project is a hands-on CCA-F study lesson.
  Code must not just work — it must teach.

### CCA-F Domain Coverage — This Agent
This agent directly covers **Domain 1: Agentic Architecture & Orchestration** (~25% of exam).

When writing or explaining code, Claude Code must:
1. **Label CCA-F concepts inline** using comments like:
   `# CCA-F Domain 1: This is the core agentic loop — LLM + loop + tools + memory`
2. **Explain WHY** each design decision exists, not just what it does
3. **Flag interview talking points** with `# INTERVIEW:` comments at key lines
4. **Connect code to exam domains** — if a pattern maps to a CCA-F domain, say so
5. **Never just write code silently** — every non-trivial function gets a docstring
   that explains the concept it demonstrates

### CCA-F Exam Domains (for reference across all agents)
| Domain | Weight | This agent covers |
|--------|--------|------------------|
| Agentic Architecture & Orchestration | ~25% | ✅ Core loop, tool use, session mgmt |
| Tool Design & MCP Integration | ~20% | ✅ Tool registry, error handling |
| Claude Code Config & Workflows | ~20% | ✅ This CLAUDE.md itself |
| Prompt Engineering & Structured Output | ~20% | ✅ ReAct prompt, output parsing |
| Context Management & Reliability | ~15% | ✅ Statelessness, full history per call |

---

## Obsidian Logging Convention
Claude Code must log every significant action to the Obsidian daily note at:
`C:\Users\subin\obsidianvault\Daily Notes\YYYY-MM-DD.md`

Always append under the **"🤖 Claude Code Actions"** section using this format:
```
`HH:MM` 🤖 **action_name** — brief detail of what was done
```

Examples:
```
`06:35` 🤖 **created** — agent.py with core ReAct loop, 87 lines
`07:10` 🤖 **updated** — tools.py, added search_web tool with DuckDuckGo
`07:45` 🤖 **fixed** — parsing bug in ReAct output, Action Input now handles nested JSON
```

Never log under the 🧠 JARVIS section — that is reserved for the claude.ai chat session.

---

## Hard Constraints
- NO LangChain, LangGraph, CrewAI, or any agent framework
- NO wrapper libraries around tool calling
- Raw Anthropic Python SDK only (`anthropic` package)
- Python 3.11+
- Every design decision must be explainable in an interview

---

## Architecture to Build

### The Core Loop
```
while not done:
    observation → LLM → thought → action → execute tool → observation
```
# CCA-F Domain 1: This loop IS what an agent is. Memorise this structure.

### Files to create
```
agent1/
├── agent.py          # Core ReAct loop
├── tools.py          # Tool registry + 3 tools
├── llm.py            # Raw Anthropic API wrapper
├── memory.py         # In-context message history
├── main.py           # Entry point
└── README.md         # Architecture diagram + how to run
```

### Three Tools (implement in tools.py)
1. `search_web(query: str) -> str` — use DuckDuckGo or SerpAPI
2. `calculate(expression: str) -> str` — safe eval for math
3. `get_current_date() -> str` — returns today's date

### Tool Registry Pattern
```python
TOOLS = {
    "search_web": search_web,
    "calculate": calculate,
    "get_current_date": get_current_date,
}
```
# CCA-F Domain 2: Tool design — name, description, parameters, return format.
# INTERVIEW: Explain how the LLM decides which tool to call based on descriptions.

### ReAct Prompt Structure
The system prompt must instruct the LLM to output in this format:
```
Thought: [reason about what to do]
Action: tool_name
Action Input: {"param": "value"}
```
Then parse that output, execute the tool, inject:
```
Observation: [tool result]
```
And loop until the LLM outputs `Final Answer:`.
# CCA-F Domain 4: This is structured output + prompt engineering in action.
# INTERVIEW: ReAct = Reason + Act interleaved. Invented by Yao et al. 2022.

---

## Anthropic API Usage
- Model: `claude-sonnet-4-5` (use `claude-opus-4-5` for final demo)
- Use tool_use / function calling via raw API (not wrappers)
- Handle streaming if needed but not required for v1
- Always include full message history in each API call (LLMs are stateless)
# CCA-F Domain 5: Statelessness is fundamental. Every call sends the full history.
# INTERVIEW: Why does every call include the full history? Because LLMs have no memory.

---

## Code Style
- Type hints on all functions
- Docstrings on all classes and public methods — must explain the CCA-F concept demonstrated
- No global state except TOOLS registry
- Exceptions must be caught at tool execution level, not swallowed silently
- Print each Thought / Action / Observation to console so the loop is visible
- Add `# CCA-F DomainN:` comments at every architecturally significant line
- Add `# INTERVIEW:` comments at lines that would make strong interview talking points

---

## What success looks like
Running `python main.py "What is the population of Dubai and what is 15% of it?"` should:
1. Think about what tools to use
2. Call search_web for Dubai population
3. Call calculate for the 15% math
4. Return a final answer
All steps visible in console output.

---

## Context: 100 Agents Project
This is Agent 1 of 100. The goal is a portfolio of production-grade agents
demonstrating deep understanding of agentic internals — not framework usage.

Each agent maps to a CCA-F domain:
| Agent | Focus | CCA-F Domain |
|-------|-------|-------------|
| 1 (this) | Raw ReAct, pure Python | Domain 1 — Agentic Architecture |
| 2 | Memory systems from scratch | Domain 5 — Context Management |
| 3 | LangChain Q&A Bot | Domain 1 deep |
| 4 | CV Optimizer Agent | Domain 4 — Prompt Engineering |
| 5 | Job Hunt Agent (LangGraph) | Domain 1 — Orchestration |
| 6 | Multi-Agent Research Bot | Domain 2 — Tool Design |
| 7 | Auto-Eval Pipeline | Domain 3 — Claude Code |
| 8 | Production RAG Service | Domain 5 deep |

GitHub repo for portfolio: to be created.
Each agent: README + architecture diagram + demo video.
