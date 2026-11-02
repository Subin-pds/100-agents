"""Core ReAct loop for Agent 4 — Research Summariser.

CCA-F Domain 1 — Agentic Architecture & Orchestration:
    Agent 4 extends the ReAct pattern (Agent 1) with a research workflow.
    Key difference: the agent uses *tool chaining* — search_web results
    feed into save_to_obsidian, creating a pipeline inside the agent loop.

    Tool chaining: one tool's output informs another tool's input.
    This is distinct from parallel tool use (multiple tools simultaneously).

INTERVIEW: What is tool chaining vs parallel tool use?
    Chaining: Tool A's output is used to construct Tool B's input.
             (search → synthesise → save)
    Parallel: Multiple tools called simultaneously in one LLM response.
             (search query 1 + search query 2 at the same time)
    Anthropic's API supports both — parallel calls appear as multiple
    tool_use blocks in one response. Chaining spans multiple iterations.
"""

import json
from typing import Any

import anthropic

from .tools import TOOL_SCHEMAS, execute_tool

# CCA-F Domain 4 — Prompt Engineering:
# The system prompt is the agent's constitution. It defines:
# 1. Persona (what the agent is)
# 2. Workflow (the steps to follow)
# 3. Output format (structured note template)
# 4. Rules (constraints that prevent common failure modes)
# INTERVIEW: Why is the note format in the system prompt rather than user message?
# System prompts set stable behavioural rules across all turns. Putting the
# format there means it applies regardless of how the user phrases the request.
SYSTEM_PROMPT = """\
You are a Research Summariser Agent. Your job: systematically research a topic,
synthesise findings, and save a structured Markdown note to Obsidian.

Workflow — follow this exactly:
1. Call get_current_date() to get today's date for the note frontmatter.
2. Break the topic into 3–5 focused search queries (think: different angles/subtopics).
3. Call search_web() for each query. Run searches one at a time.
4. After all searches, synthesise everything into a structured note.
5. Call save_to_obsidian() with the title and the complete note content.
6. Report what was saved and give a one-paragraph summary.

Note format to use inside save_to_obsidian(content=...):
---
date: YYYY-MM-DD
topic: {TOPIC}
agent: Agent 4 — Research Summariser
searches: {N}
---

# {TOPIC}

## Summary
{2–3 paragraphs synthesising all findings. Be specific — name facts, figures, dates.}

## Key Findings
- {finding 1}
- {finding 2}
- {finding 3}
- {add more as needed}

## Searches Performed
- {query 1}
- {query 2}
- {query 3}

#research #agent4 #{topic-as-tag}

Rules:
- Always search before synthesising. Never fabricate facts.
- Run get_current_date() first, before any searches.
- Call save_to_obsidian() exactly once, after all searches are done.
- If a search returns no result, try a rephrased query.
"""

# CCA-F Domain 1: MAX_ITERATIONS is a hard safety ceiling.
# INTERVIEW: What happens without MAX_ITERATIONS? The agent can loop forever
# on a stubborn problem, burning tokens and money. Always set a ceiling.
# 12 iterations allows: 1 date + 5 searches + 1 save + 5 retries.
MAX_ITERATIONS = 12


class ResearchAgent:
    """ReAct agent that researches a topic and saves a structured Obsidian note.

    CCA-F Domain 1 — The Four Parts of an Agent:
        LLM    → self.client.messages.create()
        Loop   → the for loop in run()
        Tools  → execute_tool() in tools.py
        Memory → self.messages (full conversation history)

    This agent adds a fifth element: structured output. The system prompt
    defines a note template, and save_to_obsidian enforces it by writing
    whatever the LLM produces as the note content.

    INTERVIEW: What are the four components every agent must have?
        1. LLM — the reasoning engine
        2. Loop — the control flow that drives iterations
        3. Tools — the actions the agent can take
        4. Memory — context accumulated across iterations
    """

    def __init__(self) -> None:
        # CCA-F Domain 5: One Anthropic client per agent instance.
        # messages grows each iteration — it IS the agent's working memory.
        self.client = anthropic.Anthropic()
        self.messages: list[dict[str, Any]] = []

    def run(self, topic: str) -> str:
        """Research a topic, save a note, and return a final answer string.

        CCA-F Domain 1 — Loop Termination Conditions:
            1. stop_reason == "end_turn"  → LLM answered (success)
            2. stop_reason == "tool_use"  → LLM called tools (continue loop)
            3. MAX_ITERATIONS reached     → safety ceiling (graceful exit)

        INTERVIEW: Why have two termination conditions?
            end_turn is the happy path — the agent completed its task.
            MAX_ITERATIONS is the safety net — prevents infinite loops.
            Without the safety net, a confused or stubborn LLM could loop forever.
        """
        print(f"\n{'='*60}")
        print(f"Research Topic: {topic}")
        print(f"{'='*60}\n")

        # CCA-F Domain 5: Seed the conversation with the user's request.
        # Every subsequent API call will include this message plus all
        # tool calls and results accumulated across iterations.
        self.messages.append({"role": "user", "content": f"Research topic: {topic}"})

        for iteration in range(1, MAX_ITERATIONS + 1):
            print(f"--- Iteration {iteration} ---")

            # CCA-F Domain 5: Full history is sent on every API call.
            # The LLM has no persistent state — we provide all context
            # by resending the complete conversation each time.
            # INTERVIEW: Why does token cost grow with each iteration?
            # Because the full history grows and is resent. Mitigation strategies:
            # sliding window (truncate old messages), summarisation (compress history).
            response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOL_SCHEMAS,
                messages=self.messages,
            )

            # CCA-F Domain 1: stop_reason is the API's signal for what happened.
            # "end_turn"  → LLM finished — extract text and return.
            # "tool_use"  → LLM wants tools — execute and loop.
            # Any other   → unexpected — treat as final answer.
            if response.stop_reason == "end_turn":
                final = _extract_text(response.content)
                print(f"\nFinal Answer:\n{final}\n")
                return final

            if response.stop_reason == "tool_use":
                # CCA-F Domain 2: One response may have multiple tool_use blocks
                # (parallel tool calls). Execute all before the next iteration.
                tool_results = self._handle_tool_calls(response.content)

                # CCA-F Domain 5: The API requires alternating roles.
                # assistant message must include the tool_use blocks,
                # then a user message carries the tool_result blocks.
                # INTERVIEW: Why are tool results sent as a user message?
                # The Anthropic API models tool results as observations coming
                # from the environment (user role), not the assistant. This
                # enforces the Thought (assistant) → Observation (user) structure.
                self.messages.append({"role": "assistant", "content": response.content})
                self.messages.append({"role": "user", "content": tool_results})
                continue

            # Fallback for unexpected stop reasons.
            final = _extract_text(response.content)
            print(f"\nFinal Answer (stop_reason={response.stop_reason}):\n{final}\n")
            return final

        return (
            "Research agent reached the maximum iteration limit. "
            "Partial results may have been saved to Obsidian."
        )

    def _handle_tool_calls(
        self, content: list[Any]
    ) -> list[dict[str, Any]]:
        """Execute all tool_use blocks in a response, return tool_result blocks.

        CCA-F Domain 2 — Tool Execution Pattern:
            Each tool_use block has: id (unique), name (tool to call), input (args).
            Each tool_result block must carry the same tool_use_id — this is how
            the API links calls to results when multiple tools run in parallel.

        INTERVIEW: What is tool_use_id used for?
            It links each tool call to its result. If the LLM calls three tools
            in one response (parallel), there are three tool_use blocks and three
            tool_result blocks — matched by id. Without id matching, the LLM
            cannot tell which result belongs to which call.
        """
        results: list[dict[str, Any]] = []
        for block in content:
            if block.type == "text":
                # CCA-F Domain 1: Text blocks during tool_use are the Thought step —
                # the LLM reasoning about what to do before acting.
                if block.text.strip():
                    print(f"Thought: {block.text.strip()}")
            elif block.type == "tool_use":
                # CCA-F Domain 1: tool_use blocks are the Action step.
                args_str = json.dumps(block.input)
                # Truncate long args for console readability.
                display_args = args_str[:120] + "..." if len(args_str) > 120 else args_str
                print(f"Action : {block.name}({display_args})")

                # CCA-F Domain 2: execute_tool() is the boundary — all exceptions
                # are caught there and returned as strings.
                observation = execute_tool(block.name, block.input)

                # CCA-F Domain 1: The tool result is the Observation step.
                obs_display = str(observation)
                if len(obs_display) > 300:
                    obs_display = obs_display[:300] + "..."
                print(f"Obs    : {obs_display}\n")

                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(observation),
                })
        return results


# ---------------------------------------------------------------------------
# Module-level helper
# ---------------------------------------------------------------------------

def _extract_text(content: list[Any]) -> str:
    """Join all text blocks from a content list into a single string."""
    return "\n".join(
        block.text for block in content if hasattr(block, "text")
    ).strip()
