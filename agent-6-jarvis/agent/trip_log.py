"""Trip record persistence — one Markdown file per day in a public Google
Drive folder.

Jarvis's backend runs on Cloud Run (see api.py), which has no path to the
user's local Obsidian vault — that only exists inside a Claude Code session
on the user's own machine. Drive is the persistence layer instead: the
folder is shared "anyone with the link can view" so the file is readable
directly (matches the get_document pattern for personal docs already used
in tools.py) any time from any device, including by Claude for analysis.
Writing still requires authentication no matter how the folder is shared —
Drive's API has no anonymous-write path — so the backend authenticates as
a dedicated service account that's been given Editor access to the folder.

Each day's file is named YYYY-MM-DD.md (matches Obsidian's default daily
note naming, in case it's ever pulled into a vault) and holds simple
`Key: value` lines under a heading — trivial to parse back out for updates
without a database, while still reading as a plain note.
"""

from __future__ import annotations

import io
import os
import re
from datetime import date as date_cls
from datetime import datetime

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]

# Hardcoded — no per-trip mileage measurement, just the vehicle's known figure.
FUEL_MILEAGE_KMPL = 18

FIELDS = [
    "KM Travelled (GPS)",
    "KM Travelled (Navigated)",
    "KM Travelled (Total)",
    "Places Visited",
    "Fuel Spend",
    "Money Spend",
    "Fuel Price",
    "Est. Fuel Used (L)",
    "Last Updated",
]


def _service():
    creds = Credentials.from_service_account_file(
        os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"], scopes=SCOPES,
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _find_file_id(service, day: str) -> str | None:
    resp = service.files().list(
        q=(
            f"name = '{day}.md' and "
            f"'{os.environ['TRIP_LOG_DRIVE_FOLDER_ID']}' in parents and "
            "trashed = false"
        ),
        fields="files(id)",
        pageSize=1,
    ).execute()
    files = resp.get("files", [])
    return files[0]["id"] if files else None


def _read_content(service, file_id: str) -> str:
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, service.files().get_media(fileId=file_id))
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue().decode("utf-8")


def _parse(content: str) -> dict[str, str]:
    fields = {}
    for line in content.splitlines():
        match = re.match(r"^([A-Za-z .()]+):\s*(.*)$", line)
        if match and match.group(1) in FIELDS:
            fields[match.group(1)] = match.group(2).strip()
    return fields


def _render(day: str, fields: dict[str, str]) -> str:
    lines = [f"# Trip Log — {day}", ""]
    lines += [f"{name}: {fields.get(name, '')}" for name in FIELDS]
    return "\n".join(lines) + "\n"


def _write(service, day: str, fields: dict[str, str], file_id: str | None) -> None:
    content = _render(day, fields)
    media = MediaIoBaseUpload(io.BytesIO(content.encode("utf-8")), mimetype="text/markdown")
    if file_id:
        service.files().update(fileId=file_id, media_body=media).execute()
    else:
        service.files().create(
            body={
                "name": f"{day}.md",
                "parents": [os.environ["TRIP_LOG_DRIVE_FOLDER_ID"]],
                "mimeType": "text/markdown",
            },
            media_body=media,
        ).execute()


def _load(service, day: str) -> tuple[dict[str, str], str | None]:
    file_id = _find_file_id(service, day)
    fields = _parse(_read_content(service, file_id)) if file_id else {}
    return fields, file_id


def _num(value: str | None) -> float:
    match = re.match(r"[\d.]+", value or "")
    return float(match.group()) if match else 0.0


def _recompute_total(fields: dict[str, str]) -> None:
    """KM Travelled (Total) = GPS-tracked + navigate_to route estimates.

    These come from two independent write paths (client GPS overwrite vs.
    navigate_to's additive route lookup, see update_km_travelled and
    add_navigated_distance below) that never touch each other's field, so
    the total is always just their sum, recomputed on every write.
    """
    total = _num(fields.get("KM Travelled (GPS)")) + _num(fields.get("KM Travelled (Navigated)"))
    fields["KM Travelled (Total)"] = f"{round(total, 2)} km"
    fields["Est. Fuel Used (L)"] = f"{round(total / FUEL_MILEAGE_KMPL, 2)} L (at {FUEL_MILEAGE_KMPL} km/L)"


def update_km_travelled(km_travelled: float, day: str | None = None) -> None:
    """Overwrite today's GPS-tracked distance with the client's running
    cumulative total — the client owns that sum (see static/index.html's
    trip tracker), this always replaces rather than adds to it. Distance
    from navigate_to hand-offs is tracked separately (add_navigated_distance)
    since GPS tracking in the Jarvis tab pauses once Maps takes over.
    """
    day = day or date_cls.today().isoformat()
    service = _service()
    fields, file_id = _load(service, day)
    fields["KM Travelled (GPS)"] = f"{round(km_travelled, 2)} km"
    _recompute_total(fields)
    fields["Last Updated"] = datetime.now().isoformat(timespec="seconds")
    _write(service, day, fields, file_id)


def add_navigated_distance(km: float, day: str | None = None) -> None:
    """Add a routed-distance estimate for a navigate_to hand-off. Additive
    (unlike update_km_travelled) since multiple navigations can happen in
    one day, each contributing its own leg.
    """
    day = day or date_cls.today().isoformat()
    service = _service()
    fields, file_id = _load(service, day)
    fields["KM Travelled (Navigated)"] = f"{round(_num(fields.get('KM Travelled (Navigated)')) + km, 2)} km"
    _recompute_total(fields)
    fields["Last Updated"] = datetime.now().isoformat(timespec="seconds")
    _write(service, day, fields, file_id)


def log_trip_details(
    places: list[str] | None = None,
    fuel_spend: float | None = None,
    money_spend: float | None = None,
    fuel_price_info: str | None = None,
    day: str | None = None,
) -> None:
    """Append places visited / add to cumulative spend for today's file."""
    day = day or date_cls.today().isoformat()
    service = _service()
    fields, file_id = _load(service, day)

    if places:
        seen = [p.strip() for p in fields.get("Places Visited", "").split(",") if p.strip()]
        for place in places:
            if place not in seen:
                seen.append(place)
        fields["Places Visited"] = ", ".join(seen)

    if fuel_spend is not None:
        fields["Fuel Spend"] = str(round(_num(fields.get("Fuel Spend")) + fuel_spend, 2))

    if money_spend is not None:
        fields["Money Spend"] = str(round(_num(fields.get("Money Spend")) + money_spend, 2))

    if fuel_price_info:
        fields["Fuel Price"] = fuel_price_info

    fields["Last Updated"] = datetime.now().isoformat(timespec="seconds")
    _write(service, day, fields, file_id)
