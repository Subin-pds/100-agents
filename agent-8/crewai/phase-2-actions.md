# Agent 8 (CrewAI) — Phase 2 Actions

Phase 1 (done): a three-agent career crew — Trends Researcher and MAANG Jobs
Analyst run in parallel, Career Advisor turns both reports plus `../profile.md`
into a 12-month plan. Runs free on Gemini with automatic model fallback
(`llm_fallback.py`).

Phase 2 makes it an ongoing personal career coach. Each step teaches one new
CrewAI concept.

## Before anything else
- [ ] Fill every `TODO` in `../profile.md` (experience, education, target role/level,
      DSA level, cert status, weekly study hours) — the plan is only as personal as this file

## Roadmap

| # | Feature | Concept | Why |
|---|---|---|---|
| 4 | Structured output + guardrails | `output_pydantic`, `guardrail` | Jobs report currently claims skill counts ("10/10 postings") it can't back up; force a typed list of postings and reject counts that don't match |
| 5 | MCP: Obsidian vault | `Agent(mcps=[...])` | Save each plan into the vault; read daily notes to see what was actually done this week |
| 6 | MCP: GitHub Portfolio Auditor (4th agent) | MCP as tools, evidence-based profiling | Assess skills from real repos/commits instead of self-reported TODOs |
| 7 | Memory + weekly progress check-in | `Crew(memory=True)` | "Last week's plan vs what you did" → adjust this week's plan |
| 8 | Flow with router + human approval | CrewAI Flows (`@start/@listen/@router`), `human_input=True` | Re-research when the jobs report is thin; approve the plan before saving. Direct comparison with LangGraph |
| 9 | Crew exposed as an MCP server + weekly schedule | FastMCP, scheduler | Ask Claude "what should I study this week?" and it runs the crew; plan auto-delivered weekly |

## More specialist agents (pick after step 6)
- **Interview Prep Coach** — weekly DSA set by pattern, one ML system-design prompt, one behavioural question; tracks scores
- **Resume Tailor** — rewrite resume bullets against a pasted job posting
- **Learning Curator** — best current course / paper / video for each gap in the plan

## Production polish (later)
- Knowledge sources: resume PDF as RAG context (`knowledge_sources`)
- Observability: self-hosted Langfuse or Arize Phoenix tracing
- Deployment: FastAPI + Docker, weekly schedule, plan delivered to Telegram

## Known issues from Phase 1 runs
- `gemini-2.5-flash` free quota runs out quickly (429); most calls end up on flash-lite
- Jobs analyst reads search snippets, not full postings, for non-Amazon companies
- Some posting URLs are search pages rather than individual jobs (Microsoft) or mismatched (Netflix)
- Trends sources are mostly aggregator sites rather than primary sources
