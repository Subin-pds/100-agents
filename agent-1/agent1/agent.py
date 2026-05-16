"""Core ReAct loop for Agent 1.

CCA-F Domain 1 — Agentic Architecture & Orchestration:
    This file contains the heart of an agent: the loop that drives
    Reasoning and Acting until a final answer is reached.

    ReAct (Yao et al., 2022) interleaves Thought → Action → Observation
    repeatedly. This implementation uses Anthropic's native tool-use API
    rather than parsing freeform text, making it more robust and production-ready.
"""

# INTERVIEW: What is ReAct? A prompting paradigm where the LLM alternates
# between Reasoning (thinking about what to do) and Acting (calling a tool).
# The result of each action (Observation) is fed back into the next reasoning
# step. Paper: "ReAct: Synergizing Reasoning and Acting in Language Models."

import json
from typing import Any

import anthropic

from .llm import call_llm
from .memory import MessageHistory
from .tools import TOOL_SCHEMAS, execute_tool

# CCA-F Domain 4 — Prompt Engineering:
# The system prompt defines the agent's persona, available tools, and
# behavioural constraints. It is sent on every API call as the 'system' field —
# separate from the conversation messages. Clear, specific instructions reduce
# hallucination and off-task behaviour.
SYSTEM_PROMPT = """\
You are a ReAct agent. For every user question you MUST reason step-by-step
using the available tools before giving a final answer.

You have these tools:
- search_web(query): Search the internet for current information.
- calculate(expression): Evaluate a math expression safely.
- get_current_date(): Get today's date.

Use tools as many times as needed. When you have enough information to answer
the user's question completely, reply with your final answer in plain prose.
Do not guess — use tools to verify facts and numbers.
"""

# CCA-F Domain 1: MAX_ITERATIONS is a stopping condition — a safety rail that
# prevents infinite loops. Real agents must always have an exit condition.
# INTERVIEW: What happens if you don't set a max iteration limit? The agent
# can loop forever, burning tokens and money. Always set a hard ceiling.
MAX_ITERATIONS = 10


class ReactAgent:
    """A single-threaded ReAct agent using the raw Anthropic tool-use API.

    CCA-F Domain 1 — The Agent Loop:
        An agent is: LLM + loop + tools + memory.
        - LLM:    call_llm() in llm.py
        - Loop:   the while/for loop in run()
        - Tools:  execute_tool() in tools.py
        - Memory: MessageHistory in memory.py

    This class wires all four together. That's all an agent is.
    """

    def __init__(self) -> None:
        # CCA-F Domain 5: One MessageHistory per agent instance = one
        # conversation session. The history grows with each iteration.
        self.history = MessageHistory()

    def run(self, user_query: str) -> str:
        """Run the ReAct loop for a user query and return the final answer.

        CCA-F Domain 1 — The Core Loop:
            while not done:
                observation → LLM → thought → action → execute tool → observation

        The loop terminates when:
        1. stop_reason == "end_turn"  — LLM chose to answer (success)
        2. MAX_ITERATIONS reached     — safety ceiling (failure graceful)
        """
        print(f"\n{'='*60}")
        print(f"User: {user_query}")
        print(f"{'='*60}\n")

        # CCA-F Domain 5: The first user message seeds the conversation.
        # Every subsequent API call will include this message plus all
        # tool calls and results accumulated so far.
        self.history.add_user(user_query)

        for iteration in range(1, MAX_ITERATIONS + 1):
            print(f"--- Iteration {iteration} ---")

            # CCA-F Domain 5: Full history is sent every iteration.
            # The LLM has no memory of previous calls — we provide it all.
            # INTERVIEW: Why does token cost grow with each iteration?
            # Because we re-send the entire history. This is the cost of
            # statelessness. Strategies: sliding window, summarisation (Agent 2).
            response = call_llm(
                messages=self.history.all(),
                system=SYSTEM_PROMPT,
                tools=TOOL_SCHEMAS,
            )

            # CCA-F Domain 1: stop_reason is how the API tells us what happened.
            # "end_turn"  → LLM produced a final answer, no more tools needed.
            # "tool_use"  → LLM wants to call one or more tools.
            # INTERVIEW: Why use stop_reason rather than regex-parsing the text?
            # Native tool-use API is structured — no brittle text parsing needed.
            # It handles edge cases (JSON in strings, multi-tool calls) reliably.

            if response.stop_reason == "end_turn":
                final_text = self._extract_text(response.content)
                print(f"\nFinal Answer: {final_text}\n")
                return final_text

            if response.stop_reason == "tool_use":
                # CCA-F Domain 2: One response can contain multiple tool_use
                # blocks (parallel tool calls). We execute all of them before
                # looping — this is more efficient than one tool per iteration.
                tool_results = self._handle_tool_calls(response.content)

                # CCA-F Domain 5: Store the assistant's tool_use blocks first,
                # then inject tool_result blocks as a user message. The API
                # requires this exact alternating structure — assistant then user.
                self.history.add_assistant(response.content)
                self.history.add_user(tool_results)
                continue

            # Fallback: unexpected stop_reason — treat as final answer.
            final_text = self._extract_text(response.content)
            print(f"\nFinal Answer (unexpected stop): {final_text}\n")
            return final_text

        return "Agent reached the maximum number of iterations without a final answer."

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _handle_tool_calls(
        self, content: list[Any]
    ) -> list[dict[str, Any]]:
        """Execute every tool_use block and return a list of tool_result dicts.

        CCA-F Domain 2 — Tool Execution Pattern:
            The Anthropic API returns tool calls as structured content blocks
            with type="tool_use". Each block has: id, name, input (dict).
            Results must be returned as type="tool_result" blocks keyed by
            the same tool_use_id — this is how the API links call to result.
        """
        # INTERVIEW: What is the tool_use_id for? It links each tool call to
        # its result. If the LLM calls two tools in parallel, there are two
        # tool_use blocks and two tool_result blocks — matched by id.
        results: list[dict[str, Any]] = []
        for block in content:
            if block.type == "text":
                # CCA-F Domain 1: Text blocks during tool_use are the
                # "Thought" step — the LLM reasoning about what to do.
                print(f"Thought: {block.text.strip()}")
            elif block.type == "tool_use":
                # CCA-F Domain 1: tool_use blocks are the "Action" step.
                tool_name = block.name
                tool_input = block.input
                print(f"Action: {tool_name}({json.dumps(tool_input)})")
                observation = execute_tool(tool_name, tool_input)
                # CCA-F Domain 1: The tool result is the "Observation" step.
                print(f"Observation: {observation}\n")
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": observation,
                    }
                )
        return results

    @staticmethod
    def _extract_text(content: list[Any]) -> str:
        """Pull plain text out of a content block list."""
        parts = [block.text for block in content if hasattr(block, "text")]
        return "\n".join(parts).strip()
