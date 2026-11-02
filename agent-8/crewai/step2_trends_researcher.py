"""Step 2 — one agent with tools: the AI Trends Researcher.

New concepts vs step 1:
  - @tool functions handed to an Agent (see tools.py)
  - the agent's internal Thought -> Tool -> Observation loop, capped by max_iter
  - {placeholders} in a Task filled by crew.kickoff(inputs=...)
  - output_file to persist the result

Run:
    venv\\Scripts\\python step2_trends_researcher.py
"""

import datetime
import os
import sys
from crewai import LLM, Agent, Crew, Task
from dotenv import load_dotenv

from tools import fetch_page, news_search, web_search

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# Free-tier Gemini by default; set LLM_MODEL in .env to switch providers.
llm = LLM(model=os.getenv("LLM_MODEL", "gemini/gemini-2.5-flash"))

trends_researcher = Agent(
    role="AI Technology Trends Researcher",
    goal=(
        "Find what actually changed in the AI engineering landscape recently — "
        "new models, frameworks, tools, protocols and certifications — and separate "
        "durable shifts from hype"
    ),
    backstory=(
        "You are a staff engineer who writes a weekly AI-engineering briefing read by "
        "hiring managers at Google, Meta and Amazon. You only report what you can cite, "
        "you prefer primary sources (release notes, official blogs) over listicles, "
        "and you always say how fresh a piece of information is."
    ),
    tools=[web_search, news_search, fetch_page],
    llm=llm,
    # Each tool call is one loop iteration; 15 leaves room for ~10 searches
    # plus a few page reads without letting a confused agent spin forever.
    max_iter=15,
    verbose=True,
)

trends_task = Task(
    description=(
        "Today is {today}. Research the AI engineering landscape over the last 3 months.\n"
        "Cover:\n"
        "1. New or significantly updated LLMs and what they are good at\n"
        "2. Agent frameworks, SDKs and protocols gaining or losing adoption (e.g. MCP, A2A)\n"
        "3. New developer tools and infra (eval, observability, inference, vector DBs)\n"
        "4. AI certifications that are new, popular, or valued by big-tech hiring\n"
        "5. Skills that are becoming table stakes vs. ones that are fading\n\n"
        "Run several searches with different phrasings, use News Search for anything "
        "time-sensitive, and read at least two full pages for depth."
    ),
    expected_output=(
        "A markdown briefing with one section per numbered topic. Each item: name, "
        "one-line what/why it matters, and a source URL. End with a 'Signal vs Hype' "
        "section ranking the 5 most durable trends."
    ),
    agent=trends_researcher,
    output_file="reports/ai_trends.md",
)

crew = Crew(agents=[trends_researcher], tasks=[trends_task], tracing=False, verbose=True)

if __name__ == "__main__":
    result = crew.kickoff(inputs={"today": datetime.date.today().isoformat()})
    print("\n" + "=" * 60)
    print("Saved to reports/ai_trends.md")
    print(f"Token usage: {result.token_usage}")
