"""Tools for Agent 6 — Jarvis, the in-car assistant.

Four tool groups: general web search, weather, music (Spotify), and
navigation (OpenStreetMap geocoding + a Google Maps deep link). Navigation
deliberately avoids the paid Google Places/Routes APIs — geocoding via
Nominatim and handing off to Maps via a URL both work with zero API key
and zero billing setup, which matters for a personal project.
"""

import os
from typing import Literal

import requests
from ddgs import DDGS
from langchain_core.tools import tool

from . import trip_log

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
# http, not https — ip-api.com's free tier doesn't support TLS. Low-stakes
# for a city-level location guess; ipapi.co (https) was tried first but its
# free tier rate-limits aggressively and returned 429 in testing.
IPAPI_URL = "http://ip-api.com/json/"
# Nominatim's usage policy requires a descriptive User-Agent identifying the app.
USER_AGENT = "agent-6-jarvis/0.1 (personal project)"

# Open-Meteo weather codes -> short human descriptions (subset covering common cases).
WEATHER_CODES = {
    0: "clear sky", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "fog", 51: "light drizzle", 61: "light rain", 63: "rain",
    65: "heavy rain", 71: "light snow", 73: "snow", 75: "heavy snow",
    80: "rain showers", 95: "thunderstorm",
}


def _geocode(place: str) -> dict | None:
    """Resolve a place name to lat/lon + display name via Nominatim."""
    resp = requests.get(
        NOMINATIM_URL,
        params={"q": place, "format": "json", "limit": 1},
        headers={"User-Agent": USER_AGENT},
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json()
    return results[0] if results else None


@tool
def web_search(query: str) -> str:
    """Search the web for information on a query and return a text summary.

    Use this for general knowledge questions Jarvis can't answer directly
    or that need current information (news, facts, prices, etc.).
    """
    try:
        results = list(DDGS().text(query, max_results=5))
    except Exception as exc:
        return f"Search error: {exc}"

    if not results:
        return "No result found for that query."

    return "\n\n".join(
        f"{r['title']}\n{r['body']}\n{r['href']}" for r in results
    )


@tool
def get_current_location() -> str:
    """Get the user's current approximate location (city, region, country).

    Use this whenever the user says "here", "nearby", "right now" without
    naming a place, or asks for "the nearest X" — resolve it to a real
    place first, then pass that place into get_weather/navigate_to.

    Checks the JARVIS_LOCATION env var first — set it to override IP
    geolocation, which resolves to the ISP's routing point rather than the
    actual device and can be tens of km off (confirmed in testing: showed
    a neighbouring city to the real one). A real car deployment should get
    exact coordinates from the phone's GPS instead of either of these.
    """
    override = os.environ.get("JARVIS_LOCATION")
    if override:
        return f"Current location: {override}."

    try:
        resp = requests.get(IPAPI_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "success":
            return "Couldn't determine current location."
        city = data.get("city")
        region = data.get("regionName")
        country = data.get("country")
        return f"Approximate current location: {city}, {region}, {country} (IP-based, may be inaccurate)."
    except Exception as exc:
        return f"Couldn't determine current location: {exc}"


@tool
def get_weather(location: str) -> str:
    """Get the current weather for a location (city/place name)."""
    place = _geocode(location)
    if not place:
        return f"Couldn't find a location matching '{location}'."

    resp = requests.get(
        OPEN_METEO_URL,
        params={
            "latitude": place["lat"],
            "longitude": place["lon"],
            "current": "temperature_2m,weather_code,wind_speed_10m",
        },
        timeout=10,
    )
    resp.raise_for_status()
    current = resp.json().get("current", {})
    code = current.get("weather_code")
    condition = WEATHER_CODES.get(code, "unknown conditions")
    return (
        f"Weather in {place['display_name'].split(',')[0]}: "
        f"{current.get('temperature_2m')}°C, {condition}, "
        f"wind {current.get('wind_speed_10m')} km/h."
    )


OSRM_ROUTE_URL = "https://router.project-osrm.org/route/v1/driving"


def _route_distance_km(origin: dict, destination: dict) -> float | None:
    """Driving-route distance in km via OSRM's free public demo server (no
    key — same fair-use category as the Nominatim geocoding above). Used
    only to estimate distance for navigate_to hand-offs: once Maps takes
    over, the Jarvis tab is backgrounded for the whole drive and the
    client-side GPS tracker in static/index.html can't see any of it.
    Returns None on any failure — this is a best-effort trip-log addition,
    never worth failing the actual navigation over.
    """
    try:
        resp = requests.get(
            f"{OSRM_ROUTE_URL}/{origin['lon']},{origin['lat']};{destination['lon']},{destination['lat']}",
            params={"overview": "false"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != "Ok":
            return None
        return data["routes"][0]["distance"] / 1000
    except Exception:
        return None


@tool
def navigate_to(destination: str, origin: str | None = None) -> str:
    """Get turn-by-turn navigation to a destination.

    Resolves the destination to a real place, then returns a Google Maps
    navigation link. In the car this hands off to the Maps app for actual
    turn-by-turn guidance — Jarvis doesn't do its own routing.

    Pass origin as the user's current location if you know it (the GPS
    note in this conversation's system prompt, if present — otherwise call
    get_current_location first). It's used only to estimate driving
    distance for the trip log, since GPS tracking in the Jarvis tab
    pauses for the whole drive once Maps takes over; the navigation link
    itself works fine without it, so skip it rather than guessing.
    """
    place = _geocode(destination)
    if not place:
        return f"Couldn't find a destination matching '{destination}'."

    if origin:
        origin_place = _geocode(origin)
        if origin_place:
            distance_km = _route_distance_km(origin_place, place)
            if distance_km is not None:
                try:
                    trip_log.add_navigated_distance(distance_km)
                except Exception:
                    pass  # trip log is best-effort, never blocks navigation

    maps_url = (
        f"https://www.google.com/maps/dir/?api=1"
        f"&destination={place['lat']},{place['lon']}"
        f"&travelmode=driving"
    )
    return f"Navigating to {place['display_name']}: {maps_url}"


YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


@tool
def play_music(query: str) -> str:
    """Search YouTube for a track/artist and return a link that starts
    playing it. Opens in the YouTube app on mobile (if installed) or the
    browser on desktop, and autoplays there — this hands off playback the
    same way navigate_to hands off to Maps, rather than controlling
    playback remotely (YouTube has no API for that, unlike Spotify).
    """
    try:
        resp = requests.get(
            YOUTUBE_SEARCH_URL,
            params={
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": 1,
                "key": os.environ["YOUTUBE_API_KEY"],
            },
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if not items:
            return f"No video found for '{query}'."
        item = items[0]
        video_id = item["id"]["videoId"]
        title = item["snippet"]["title"]
        url = f"https://www.youtube.com/watch?v={video_id}&autoplay=1"
        return f"Playing '{title}': {url}"
    except Exception as exc:
        return f"Couldn't play music: {exc}"


# Personal document links (Google Drive "anyone with the link"), one env
# var per doc — set only the ones the user actually wants Jarvis to open.
# Gated by the PIN check in api.py, since these are ID documents.
DOCUMENT_ENV_VARS = {
    "driving_license": "DOC_LICENSE_URL",
    "aadhar": "DOC_AADHAR_URL",
    "vehicle_rc": "DOC_VEHICLE_RC_URL",
    "pollution_certificate": "DOC_POLLUTION_URL",
}
DOCUMENT_LABELS = {
    "driving_license": "driving licence",
    "aadhar": "Aadhaar card",
    "vehicle_rc": "vehicle RC",
    "pollution_certificate": "pollution certificate",
}


@tool
def get_document(document_type: Literal["driving_license", "aadhar", "vehicle_rc", "pollution_certificate"]) -> str:
    """Open one of the user's personal documents (stored as Google Drive
    links). Use for requests like "show me my driving licence", "open my
    aadhar", "pull up the RC", "show my pollution certificate".
    """
    label = DOCUMENT_LABELS[document_type]
    url = os.environ.get(DOCUMENT_ENV_VARS[document_type])
    if not url:
        return f"No link is configured for your {label} yet."
    return f"Opening your {label}: {url}"


@tool
def log_trip(
    places_visited: list[str] | None = None,
    fuel_spend: float | None = None,
    money_spend: float | None = None,
    fuel_price_location: str | None = None,
) -> str:
    """Log trip details for today — places visited and/or money spent.

    Use whenever the user reports trip info by voice, e.g. "log that I
    stopped at Kochi", "I spent 500 on fuel", "log 200 for parking". Each
    call adds to today's running record — fuel_spend and money_spend
    accumulate across multiple calls in the same day rather than
    overwriting. Distance travelled is tracked automatically from GPS, not
    through this tool.

    When fuel_spend is given, also pass fuel_price_location (the place the
    fuel was bought — use get_current_location if the user doesn't name a
    place) so today's local fuel price can be looked up and saved
    alongside it.
    """
    fuel_price_info = None
    if fuel_spend is not None and fuel_price_location:
        try:
            results = list(
                DDGS().text(f"petrol diesel fuel price today {fuel_price_location}", max_results=1)
            )
            if results:
                fuel_price_info = f"{results[0]['title']}: {results[0]['body'][:200]}"
        except Exception:
            fuel_price_info = None

    try:
        trip_log.log_trip_details(
            places=places_visited,
            fuel_spend=fuel_spend,
            money_spend=money_spend,
            fuel_price_info=fuel_price_info,
        )
    except Exception as exc:
        return f"Couldn't save that to the trip log: {exc}"

    parts = []
    if places_visited:
        parts.append(f"added {', '.join(places_visited)} to places visited")
    if fuel_spend is not None:
        note = " with today's local fuel price saved" if fuel_price_info else ""
        parts.append(f"logged {fuel_spend} on fuel{note}")
    if money_spend is not None:
        parts.append(f"logged {money_spend} spent")
    return "Trip log updated: " + "; ".join(parts) + "." if parts else "Nothing to log."


TOOLS = [web_search, get_current_location, get_weather, navigate_to, play_music, get_document, log_trip]
