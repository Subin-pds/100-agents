"""LangGraph StateGraph for Agent 6 — Jarvis.

Same single-agent-plus-tools shape as Agent 5: one node calls Claude bound
to the full tool belt, a conditional edge routes to the tools node when a
tool call is requested, and a fixed edge closes the loop back to the agent.
The only real difference from Agent 5 is the tool belt (search, weather,
music, navigation) and a system prompt tuned for voice-first, driving-safe
answers.
"""

from typing import Annotated, TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from .tools import TOOLS

SYSTEM_PROMPT = """\
You are Jarvis, a voice assistant running in the user's car while they drive.

Rules:
- Keep answers short — 3-5 sentences. They will be read aloud while the
  user is driving; long answers are a safety problem, not a feature.
- Reply in the same language the user's message is in — if they write in
  Malayalam, reply in Malayalam; if English, reply in English. Never
  switch languages on them mid-conversation unless they do.
- Never ask the user to look at a screen or read something back to you.
- For music requests, use play_music. It opens/autoplays a link — it can't
  pause/skip/resume something already playing, so say so if asked.
- For "take me to X" / "navigate to X" requests, use navigate_to. Pass
  origin as the user's current location if you know it (from the GPS note
  below, if present) — it's used for a trip-distance estimate, not shown
  to the user, and safe to skip if you don't know it.
- For weather, use get_weather.
- get_weather and navigate_to geocode the place name via Nominatim
  (OpenStreetMap), which is far more reliable with Latin-script/English
  place names than with names in other scripts. If the user names a place
  in Malayalam (or asks in Malayalam), pass the place name to these tools
  romanized/in English (e.g. transliterate or use the common English name)
  even though your spoken reply back to the user stays in Malayalam.
- If the user says "here"/"nearby"/doesn't name a place, or asks for "the
  nearest X", call get_current_location first, then use that place.
- For anything else needing current information, use web_search. Always
  search in English, regardless of what language the user asked in — the
  web has far more indexed content in English than Malayalam, so an
  English query surfaces better/deeper results. Translate the findings
  and reply in the user's language as usual; the query itself is the only
  part that goes out in English.
- For requests to see a personal document — driving licence, aadhar,
  vehicle RC, pollution certificate — use get_document.
- When the user reports trip info by voice — a place they stopped at, fuel
  or other money spent — use log_trip. Don't wait for an explicit "log
  this"; treat casual mentions ("just filled up, 500 rupees", "we're at
  Kochi now") as a log_trip call too. Distance travelled is tracked
  automatically from GPS, so never call log_trip for that.
- If a tool call fails, say so briefly and suggest one clear next step —
  don't apologise at length.
- play_music, navigate_to, and get_document return a result containing a
  URL. Never say the URL out loud or include it in your reply — the client
  app opens it automatically on its own. Just confirm what you're doing in
  words, e.g. "Playing Never Gonna Give You Up" or "Opening your RC."
"""


class State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def build_graph():
    """Compile the Jarvis graph. Call once per process; reuse the result."""
    llm = ChatAnthropic(model="claude-sonnet-4-5", temperature=0).bind_tools(TOOLS)

    def agent_node(state: State, config: RunnableConfig) -> dict:
        messages = state["messages"]
        if not any(isinstance(m, SystemMessage) for m in messages):
            prompt = SYSTEM_PROMPT
            # api.py resolves the client's real GPS via reverse geocoding
            # and passes it here per-request — more accurate than the
            # get_current_location tool's IP-based guess, so tell the model
            # to skip that tool call when this is present.
            current_location = config.get("configurable", {}).get("current_location")
            if current_location:
                prompt += (
                    f"\n\nThe user's real current GPS location right now is: "
                    f"{current_location}. Use this directly for \"here\"/\"nearby\" "
                    f"requests instead of calling get_current_location."
                )
            current_speed_kmh = config.get("configurable", {}).get("current_speed_kmh")
            if current_speed_kmh is not None:
                prompt += (
                    f"\n\nThe user's current GPS-measured speed is "
                    f"{current_speed_kmh} km/h. Use this directly if asked how "
                    f"fast they're going — there's no tool for it, this is the "
                    f"only source. GPS speed can be null/absent even from a "
                    f"moving phone if the sensor doesn't report it yet; if this "
                    f"note is missing, say you can't tell right now rather than "
                    f"guessing a number."
                )
            messages = [SystemMessage(content=prompt), *messages]
        return {"messages": [llm.invoke(messages)]}

    graph = StateGraph(State)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(TOOLS))
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")
    return graph.compile(checkpointer=MemorySaver())
