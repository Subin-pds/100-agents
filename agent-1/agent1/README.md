# Agent 1 — Raw Python ReAct Agent

## Architecture

```
main.py
  └── ReactAgent.run(query)          # agent.py
        ├── MessageHistory           # memory.py  — full convo kept in RAM
        ├── call_llm(messages, ...)  # llm.py     — raw Anthropic API call
        └── execute_tool(name, inp)  # tools.py   — registry dispatch

ReAct Loop
──────────
User query
  │
  ▼
[ call_llm ] ──stop_reason="tool_use"──► execute_tool ──► Observation
  ▲                                                              │
  └──────────────── append to MessageHistory ◄──────────────────┘
  │
  └──stop_reason="end_turn"──► Final Answer → user
```

## Files

| File | Purpose |
|------|---------|
| `agent.py` | Core ReAct loop, iteration control, tool dispatch |
| `tools.py` | Tool registry + 3 tool implementations |
| `llm.py` | Thin wrapper around `anthropic.Anthropic.messages.create` |
| `memory.py` | `MessageHistory` — list of dicts, appended each turn |
| `main.py` | CLI entry point (one level up) |

## Tools

| Tool | What it does |
|------|-------------|
| `search_web(query)` | DuckDuckGo Instant Answer API — no key needed |
| `calculate(expression)` | AST-safe math eval |
| `get_current_date()` | `datetime.date.today().isoformat()` |

## How to run

```bash
pip install anthropic python-dotenv

# Windows PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
python main.py "What is the population of Dubai and what is 15% of it?"

# or put the key in a .env file
```

## Interview talking points

1. **Why no framework?** Forces understanding of the actual API contract — tool_use stop_reason, content block types, the assistant/user ping-pong required for tool results.
2. **Why full history every call?** LLMs are stateless; the "memory" is just the message list we keep rebuilding.
3. **Why AST-safe eval?** `eval()` on raw user strings is RCE. Walking the AST and whitelisting node types gives math without the risk.
4. **Why `stop_reason` over regex parsing?** Anthropic's native tool-use API is more reliable than parsing freeform text and doesn't break on edge cases.
