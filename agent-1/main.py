"""Entry point for Agent 1 — Raw Python ReAct Agent."""

import sys

from dotenv import load_dotenv

from agent1.agent import ReactAgent


def main() -> None:
    load_dotenv()
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else (
        "What is the population of Dubai and what is 15% of it?"
    )
    agent = ReactAgent()
    agent.run(query)


if __name__ == "__main__":
    main()
