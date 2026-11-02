"""ReAct loop that turns stored transactions into a financial advice report.

Same LLM + loop + tools + memory shape as Agent 1 — the only thing that
changes agent-to-agent is the system prompt and the tool set.
"""

from typing import Any

from .llm import call_llm
from .memory import MessageHistory
from .tools import TOOL_SCHEMAS, execute_tool

SYSTEM_PROMPT = """\
You are a personal finance advisor agent. You have tools to query a store of
the user's real GPay/bank transactions. Before giving any advice you MUST
call tools to gather real numbers — never guess or estimate figures.

Recommended order: get_summary_stats -> get_category_breakdown ->
get_monthly_trend -> get_top_merchants -> flag_unusual_spending. Call each
at most once unless you need a different month.

When you have enough data, write a structured Markdown report with these
sections:
## Overview
## Spending by Category
## Monthly Trend
## Top Merchants
## Unusual Spending
## Action Items
The Action Items section must have 3-5 concrete, specific suggestions
(not generic advice like "spend less") — reference actual categories and
rupee amounts from the data you gathered. Where possible, estimate the
monthly rupee saving each action would produce.

After writing the report, call save_report_to_obsidian ONCE with a title
like "Finance Report YYYY-MM-DD" and the full report as content. Then give
a short plain-text summary (3-5 sentences) as your final answer.
"""

MAX_ITERATIONS = 10


class FinanceAdvisor:
    def __init__(self) -> None:
        self.history = MessageHistory()

    def run(self, user_query: str) -> str:
        self.history.add_user(user_query)

        for _ in range(1, MAX_ITERATIONS + 1):
            response = call_llm(
                messages=self.history.all(),
                system=SYSTEM_PROMPT,
                tools=TOOL_SCHEMAS,
            )

            if response.stop_reason == "tool_use":
                tool_results = self._handle_tool_calls(response.content)
                self.history.add_assistant(response.content)
                self.history.add_user(tool_results)
                continue

            return self._extract_text(response.content)

        return "Advisor reached the maximum number of iterations without a final answer."

    def _handle_tool_calls(self, content: list[Any]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for block in content:
            if block.type == "text":
                print(f"Thought: {block.text.strip()}")
            elif block.type == "tool_use":
                print(f"Action: {block.name}({block.input})")
                observation = execute_tool(block.name, block.input)
                print(f"Observation:\n{observation}\n")
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": observation,
                })
        return results

    @staticmethod
    def _extract_text(content: list[Any]) -> str:
        parts = [block.text for block in content if hasattr(block, "text")]
        return "\n".join(parts).strip()
