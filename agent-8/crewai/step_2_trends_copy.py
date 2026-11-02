"""
This file is a copy of the step2_trends_researcher.py used for learning purposes. 
Objectives:
1. Get familiar with the CrewAI, the coding pattern.
2. The components, how to build an agent using CrewAI.
3. How to build multiagent set up using crewAI.
4. To know what is happening under the hood.
5. Production deployment using CrewAI
6. Understand the merit and demerits of using CrewAI
"""

import datetime
import os
import sys
from dotenv import load_dotenv
from crewai import LLM, Agent, Task, Crew
from tools_copy import web_search, news_search, read_web_page # Will create a new tools.py with a different name.


sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# Free-tier Gemini by default; set LLM_MODEL in .env to switch providers.
llm = LLM(model=os.getenv("LLM_MODEL", "gemini/gemini-2.5-flash"))

research_agent = Agent(
    role="AI technology trend researcher",
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
    tools=[web_search,news_search,read_web_page],
    llm=llm,
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
    agent=research_agent,
    output_file="reports/ai_trends_gemini_report.md",
)

crew = Crew(agents=[research_agent], tasks=[trends_task], tracing=False, verbose=True)


if __name__ == "__main__":
    result = crew.kickoff(inputs={"today":datetime.date.today().isoformat()})
    print("\n" + "=" * 60)
    print("Saved to reports/ai_trends.md")
    print(f"Token usage: {result.token_usage}")
