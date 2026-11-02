"""Research tools shared by every agent in the career crew.

DuckDuckGo (via ddgs) needs no API key, so the crew runs out of the box.
Swap in Serper/Tavily later if result quality or rate limits become a problem.
"""

import pathlib
import re

import httpx
import lxml.html
from crewai.tools import tool
from ddgs import DDGS

# Every page read is re-sent on each later loop step, so page size multiplies
# cost. 3000 chars keeps the substance of most articles at half the step-2 cost.
MAX_PAGE_CHARS = 3000

# profile.md lives at the agent-8 root so the crewai/ and langgraph/
# implementations read the same profile.
PROFILE_PATH = pathlib.Path(__file__).resolve().parent.parent / "profile.md"

# Only Amazon exposes a public JSON job feed; the others are reached through
# site-restricted web search, which finds postings but not full qualifications.
CAREER_SITES = {
    "google": "careers.google.com",
    "meta": "metacareers.com",
    "apple": "jobs.apple.com",
    "netflix": "explore.jobs.netflix.net",
    "microsoft": "careers.microsoft.com",
}
COMPANY_ALIASES = {"facebook": "meta", "alphabet": "google", "msft": "microsoft"}


def _format_results(results: list[dict], date_key: str | None = None) -> str:
    if not results:
        return "No results found. Try a broader or differently worded query."
    lines = []
    for i, r in enumerate(results, 1):
        date = f" ({r.get(date_key, '')[:10]})" if date_key else ""
        url = r.get("href") or r.get("url", "")
        lines.append(f"{i}. {r.get('title', '')}{date}\n   {url}\n   {r.get('body', '')}")
    return "\n\n".join(lines)


@tool("Web Search")
def web_search(query: str) -> str:
    """Search the web and return the top 8 results (title, URL, snippet).
    Use for evergreen questions: framework comparisons, certification details,
    skill requirements, salary ranges."""
    try:
        with DDGS() as ddgs:
            return _format_results(list(ddgs.text(query, max_results=8)))
    except Exception as exc:
        # Return the error as text so the agent can rephrase and retry
        # instead of the whole crew crashing on one flaky search.
        return f"Search failed: {exc}"


@tool("News Search")
def news_search(query: str) -> str:
    """Search news from the past month and return up to 8 dated articles.
    Use for anything time-sensitive: new model or tool launches, funding,
    hiring announcements, layoffs."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.news(query, max_results=8, timelimit="m"))
        return _format_results(results, date_key="date")
    except Exception as exc:
        return f"News search failed: {exc}"


@tool("Read Web Page")
def fetch_page(url: str) -> str:
    """Download a web page and return its main readable text (truncated).
    Use after a search when a snippet is too thin and you need the details."""
    try:
        resp = httpx.get(
            url,
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (career-research-crew)"},
        )
        resp.raise_for_status()
    except Exception as exc:
        return f"Could not fetch {url}: {exc}"

    doc = lxml.html.fromstring(resp.text)
    for bad in doc.xpath("//script|//style|//nav|//footer|//header|//noscript"):
        bad.drop_tree()
    text = " ".join(doc.text_content().split())
    return text[:MAX_PAGE_CHARS] or "Page had no readable text."


def _clean(html_text: str, limit: int) -> str:
    text = re.sub(r"<br\s*/?>", " ", html_text or "")
    text = re.sub(r"<[^>]+>", "", text)
    return " ".join(text.split())[:limit]


@tool("Amazon Jobs Search")
def amazon_jobs_search(query: str) -> str:
    """Search live Amazon job postings and return up to 6 roles with title,
    location, posted date, URL, and the basic + preferred qualifications.
    Use SHORT 2-3 word queries, e.g. 'applied scientist', 'generative AI', 'machine learning engineer'."""

    def fetch(q: str) -> list[dict]:
        resp = httpx.get(
            "https://www.amazon.jobs/en/search.json",
            params={"base_query": q, "result_limit": 6},
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()
        return resp.json().get("jobs", [])

    try:
        jobs = fetch(query)
        # Amazon requires every word to match, so long queries often return 0;
        # retrying on the first two words recovers most of them.
        if not jobs and len(query.split()) > 2:
            jobs = fetch(" ".join(query.split()[:2]))
    except Exception as exc:
        return f"Amazon jobs search failed: {exc}"

    if not jobs:
        return "No Amazon postings matched. Try a shorter or more generic role query."
    lines = []
    for i, j in enumerate(jobs, 1):
        lines.append(
            f"{i}. {j.get('title')} | {j.get('normalized_location') or j.get('location')} "
            f"| posted {j.get('posted_date')}\n"
            f"   https://www.amazon.jobs{j.get('job_path', '')}\n"
            f"   BASIC: {_clean(j.get('basic_qualifications'), 400)}\n"
            f"   PREFERRED: {_clean(j.get('preferred_qualifications'), 400)}"
        )
    return "\n\n".join(lines)


@tool("Big Tech Careers Search")
def careers_search(company: str, role: str) -> str:
    """Search one big-tech careers site for job postings.
    company must be one of: google, meta, apple, netflix, microsoft.
    role is a short role description, e.g. 'machine learning engineer generative AI'.
    Returns up to 6 postings (title, URL, snippet); use Read Web Page on a URL for details."""
    name = company.strip().lower()
    name = COMPANY_ALIASES.get(name, name)
    site = CAREER_SITES.get(name)
    if not site:
        return f"Unknown company '{company}'. Use one of: {', '.join(CAREER_SITES)}."

    results: list[dict] = []
    try:
        with DDGS() as ddgs:
            try:
                results = list(ddgs.text(f"site:{site} {role}", max_results=6))
            except Exception:
                results = []
            # Some careers sites (e.g. Google's) are barely indexed, so fall back
            # to an open search that usually surfaces the postings via aggregators.
            if not results:
                results = list(ddgs.text(f"{name} careers {role} job posting", max_results=6))
        return _format_results(results)
    except Exception as exc:
        return f"Careers search failed: {exc}"


@tool("Read Candidate Profile")
def read_profile() -> str:
    """Return the candidate's profile: current skills, experience, projects,
    certifications, target companies/roles, and weekly study time."""
    if not PROFILE_PATH.exists():
        return "No profile.md found. Advise generically and say the plan is not personalised."
    return PROFILE_PATH.read_text(encoding="utf-8")
