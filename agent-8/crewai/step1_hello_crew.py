"""Step 1 — the smallest possible CrewAI program: one Agent, one Task, one Crew.

Run:
    venv\\Scripts\\python step1_hello_crew.py
"""

import os
import sys

from crewai import LLM, Agent, Crew, Task
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# CrewAI routes "provider/model" strings to the matching provider SDK,
# so the same Agent code can swap Gemini for Claude/GPT by changing LLM_MODEL in .env.
# Gemini 2.5 Flash is the default because it runs on Google's free tier.
llm = LLM(model=os.getenv("LLM_MODEL", "gemini/gemini-2.5-flash"))

# An Agent is a persona, not a loop you write yourself. role/goal/backstory
# are templated into the system prompt CrewAI builds for the model.
career_coach = Agent(
    role="UAE GenAI Career Coach",
    goal="Give sharp, specific advice to engineers targeting senior GenAI roles in the UAE",
    backstory=(
        "You have placed dozens of AI engineers into Dubai and Abu Dhabi tech companies "
        "and know exactly what hiring managers there screen for."
    ),
    llm=llm,
    verbose=True,
)

# A Task is the unit of work. expected_output matters: it tells the agent
# when it is "done" and what shape the final answer should take.
task = Task(
    description=(
        "A mid-level GenAI engineer in India wants a senior role in the UAE paying "
        "AED 45,000/month. List the top 5 skills UAE employers screen for in 2026."
    ),
    expected_output="A numbered list of 5 skills, each with one sentence on why it matters.",
    agent=career_coach,
)

# A Crew wires agents to tasks and runs them. With one agent and one task
# it is just a single LLM call, but this is the object that scales to step 3.
crew = Crew(agents=[career_coach], tasks=[task], verbose=True)

if __name__ == "__main__":
    result = crew.kickoff()
    print("\n" + "=" * 60)
    #print(result.raw)
    print("=" * 60)
    print(f"Token usage: {result.token_usage}")
