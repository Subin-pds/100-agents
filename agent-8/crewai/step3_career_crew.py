"""Step 3 — a real multi-agent crew: three specialists, five tools, three tasks.

    Trends Researcher ──┐  (run in parallel)
                        ├──> Career Advisor (reads your profile.md) ──> career plan
    Jobs Market Analyst ┘  (advisor waits for both)

New concepts vs step 2:
  - several Agents, each with its own tool set and its own LLM
  - Task async_execution=True: the two research tasks run at the same time
  - Task context=[...]: the advisor's task receives both research outputs
  - Crew max_rpm: stays under the Gemini free-tier rate limit
  - a custom LLM class (llm_fallback.py) that switches model on 429/503/504
  - per-agent max_iter + explicit search budgets in task text to cap cost

Run:
    venv\\Scripts\\python step3_career_crew.py
"""

import datetime
import sys
import time

from crewai import Agent, Crew, Process, Task
from dotenv import load_dotenv

from llm_fallback import make_llm
from tools import (
    amazon_jobs_search,
    careers_search,
    fetch_page,
    news_search,
    read_profile,
    web_search,
)

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# Research is mostly reading and summarising, so it can run on a cheaper/free
# model; the advisor does the one piece of real reasoning, so it gets its own
# setting and can be pointed at a stronger model without touching the others.
# Each agent gets its own instance so a fallback on one doesn't move the others.
trends_llm = make_llm("RESEARCH_MODEL")
jobs_llm = make_llm("RESEARCH_MODEL")
advisor_llm = make_llm("ADVISOR_MODEL")

# ---------------------------------------------------------------- agents

trends_researcher = Agent(
    role="AI Technology Trends Researcher",
    goal="Identify the AI tools, frameworks, models and certifications that matter for big-tech AI hiring right now",
    backstory=(
        "You are a staff engineer who writes a weekly AI-engineering briefing read by "
        "hiring managers at Google, Meta and Amazon. You only report what you can cite, "
        "prefer primary sources over listicles, and separate durable shifts from hype."
    ),
    tools=[web_search, news_search, fetch_page],
    llm=trends_llm,
    max_iter=8,
    verbose=True,
)

jobs_analyst = Agent(
    role="Big Tech AI Jobs Market Analyst",
    goal="Find out what MAANG companies actually require in current AI/ML engineering job postings",
    backstory=(
        "You are a technical recruiter turned data analyst. You read job postings line by "
        "line and count which skills, qualifications and experience levels keep recurring. "
        "You trust the text of real postings over blog opinions."
    ),
    tools=[amazon_jobs_search, careers_search, fetch_page],
    llm=jobs_llm,
    max_iter=8,
    verbose=True,
)

career_advisor = Agent(
    role="Personal Career Coach for MAANG AI Roles",
    goal="Turn market research into a concrete, personalised 12-month plan that gets the candidate hired at a MAANG company",
    backstory=(
        "You have coached dozens of engineers into Google, Amazon and Meta AI teams. You are "
        "direct about gaps, you prioritise ruthlessly, and every recommendation you make is tied "
        "to evidence from the research and to the candidate's actual profile."
    ),
    tools=[read_profile],
    llm=advisor_llm,
    max_iter=4,
    verbose=True,
)

# ---------------------------------------------------------------- tasks

trends_task = Task(
    description=(
        "Today is {today}. Research the AI engineering landscape of the last 3 months.\n"
        "Cover: (1) notable new models, (2) agent frameworks and protocols gaining adoption, "
        "(3) developer tools and infra (eval, observability, inference), "
        "(4) AI certifications valued by big-tech hiring, "
        "(5) skills becoming table stakes vs fading.\n\n"
        "BUDGET: at most 5 searches and 2 page reads in total. Stop searching once each "
        "topic has at least one cited item."
    ),
    expected_output=(
        "A concise markdown briefing: one section per topic, 2-4 bullets each, every bullet "
        "with a source URL and date. End with 'Top 5 durable trends' ranked."
    ),
    agent=trends_researcher,
    # Runs in a background thread; the crew moves straight on to jobs_task
    # instead of waiting for this one to finish.
    async_execution=True,
    output_file="reports/step3/1_ai_trends.md",
)

jobs_task = Task(
    description=(
        "Today is {today}. Analyse current AI/ML engineering job postings at MAANG companies "
        "(Meta, Apple, Amazon, Netflix, Google; include Microsoft).\n"
        "Use Amazon Jobs Search for Amazon (it returns full qualifications) and Big Tech "
        "Careers Search for the others. Look at roles such as ML Engineer, Applied Scientist, "
        "GenAI / LLM engineer, and AI-focused SDE.\n\n"
        "BUDGET: at most 6 searches and 2 page reads in total."
    ),
    expected_output=(
        "A markdown report with: (1) a table of 8-12 real postings (company, title, level if "
        "visible, location, URL); (2) the most frequently required skills and tools, ranked, "
        "with how many postings mention each; (3) typical experience / degree requirements; "
        "(4) 3 notable hiring trends."
    ),
    agent=jobs_analyst,
    async_execution=True,
    # Explicitly independent: running in parallel, the trends report doesn't
    # exist yet when this task starts, so it must not depend on it.
    context=[],
    output_file="reports/step3/2_maang_jobs.md",
)

plan_task = Task(
    description=(
        "Read the candidate's profile with the Read Candidate Profile tool. Then, using the "
        "AI trends briefing and the MAANG jobs report you have been given as context, build "
        "a personalised career plan. Base every recommendation on evidence from those two "
        "reports and on the profile — do not invent the candidate's experience. Where the "
        "profile says TODO, state the assumption you made."
    ),
    expected_output=(
        "A markdown career plan with sections:\n"
        "1. Where you stand — strengths vs MAANG requirements (honest gap table: skill, "
        "required by, your level, gap size)\n"
        "2. What to learn — top 5 skills/technologies ranked by impact, each with why and a "
        "concrete resource\n"
        "3. Certifications — which to take, which to skip, and why\n"
        "4. Portfolio — which upcoming agents to build to close the gaps\n"
        "5. Interview prep — DSA, system design, ML design, behavioural\n"
        "6. 12-month roadmap — quarter by quarter, with measurable milestones\n"
        "7. This week — 3 concrete actions"
    ),
    agent=career_advisor,
    # context is what makes this a pipeline: both research outputs are injected
    # into the advisor's prompt. Because this task is synchronous, the crew
    # first waits for both parallel tasks to finish (the "join").
    context=[trends_task, jobs_task],
    output_file="reports/step3/3_career_plan.md",
)

crew = Crew(
    agents=[trends_researcher, jobs_analyst, career_advisor],
    tasks=[trends_task, jobs_task, plan_task],
    process=Process.sequential,
    # Gemini's free tier caps requests per minute; CrewAI waits instead of
    # letting the API reject calls once this many have been made in a minute.
    max_rpm=8,
    tracing=False,
    verbose=True,
)

if __name__ == "__main__":
    started = time.perf_counter()
    result = crew.kickoff(inputs={"today": datetime.date.today().isoformat()})
    print("\n" + "=" * 60)
    print(f"Wall-clock time: {time.perf_counter() - started:.0f}s")
    for task_output in result.tasks_output:
        print(f"{task_output.agent:45} -> {len(task_output.raw):6,} chars")
    print("Reports saved under reports/step3/")
    print(f"Token usage: {result.token_usage}")
