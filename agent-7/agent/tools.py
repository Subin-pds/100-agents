"""Tool registry for Agent 7 — Personal Finance Advisor.

Read tools query the SQLite store built by ingest.py. The one write tool
saves the final advice report to Obsidian, mirroring Agent 4's pattern.
"""

import os
import pathlib

from . import store

DB_PATH = pathlib.Path(os.getenv("FINANCE_DB_PATH", "data/transactions.db"))

OBSIDIAN_VAULT = pathlib.Path(
    os.getenv("OBSIDIAN_VAULT_PATH", r"C:\Users\subin\obsidianvault")
)
FINANCE_NOTES_FOLDER = OBSIDIAN_VAULT / "Finance" / "Agent7"


def get_category_breakdown(month: str = "") -> str:
    rows = store.category_breakdown(DB_PATH, month or None)
    if not rows:
        return "No spending data found for that period."
    lines = [f"{cat}: ₹{total:,.2f}" for cat, total in rows]
    return "\n".join(lines)


def get_monthly_trend(months: int = 6) -> str:
    rows = store.monthly_trend(DB_PATH, months)
    if not rows:
        return "No monthly data available."
    lines = [
        f"{ym}: income ₹{income:,.2f}, expense ₹{expense:,.2f}, net ₹{income - expense:,.2f}"
        for ym, income, expense in rows
    ]
    return "\n".join(lines)


def get_top_merchants(month: str = "", limit: int = 10) -> str:
    rows = store.top_merchants(DB_PATH, month or None, limit)
    if not rows:
        return "No merchant data found for that period."
    lines = [f"{name}: ₹{total:,.2f} across {n} transaction(s)" for name, total, n in rows]
    return "\n".join(lines)


def get_summary_stats(month: str = "") -> str:
    s = store.summary_stats(DB_PATH, month or None)
    return (
        f"Income: ₹{s['income']:,.2f}\n"
        f"Expense: ₹{s['expense']:,.2f}\n"
        f"Net: ₹{s['net']:,.2f}\n"
        f"Transactions: {s['transaction_count']}"
    )


def flag_unusual_spending() -> str:
    """Compare the two most recent months per category and flag any
    category that grew by more than 40% — a cheap anomaly signal that
    doesn't need a budget baseline to be useful."""
    trend = store.monthly_trend(DB_PATH, months=2)
    if len(trend) < 2:
        return "Not enough months of data to compare trends yet."

    prev_month, curr_month = trend[0][0], trend[1][0]
    prev_rows = dict(store.category_breakdown(DB_PATH, prev_month))
    curr_rows = dict(store.category_breakdown(DB_PATH, curr_month))

    flags = []
    for category, curr_total in curr_rows.items():
        prev_total = prev_rows.get(category, 0)
        if prev_total > 0 and curr_total > prev_total * 1.4:
            pct = (curr_total / prev_total - 1) * 100
            flags.append(
                f"{category}: ₹{curr_total:,.2f} in {curr_month} vs "
                f"₹{prev_total:,.2f} in {prev_month} (+{pct:.0f}%)"
            )
        elif category not in prev_rows:
            flags.append(f"{category}: new category in {curr_month}, ₹{curr_total:,.2f}")

    return "\n".join(flags) if flags else "No category grew more than 40% month-over-month."


def save_report_to_obsidian(title: str, content: str) -> str:
    FINANCE_NOTES_FOLDER.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in " -_" else "" for c in title).strip()
    safe = safe.replace(" ", "_")[:80]
    filepath = FINANCE_NOTES_FOLDER / f"{safe}.md"
    try:
        filepath.write_text(content, encoding="utf-8")
        return f"Saved: {filepath}"
    except OSError as exc:
        return f"Failed to save report: {exc}"


TOOLS: dict[str, callable] = {
    "get_category_breakdown": get_category_breakdown,
    "get_monthly_trend": get_monthly_trend,
    "get_top_merchants": get_top_merchants,
    "get_summary_stats": get_summary_stats,
    "flag_unusual_spending": flag_unusual_spending,
    "save_report_to_obsidian": save_report_to_obsidian,
}

TOOL_SCHEMAS: list[dict] = [
    {
        "name": "get_summary_stats",
        "description": "Get total income, expense, and net for a period. Call this first to ground the overview.",
        "input_schema": {
            "type": "object",
            "properties": {
                "month": {"type": "string", "description": "Optional YYYY-MM to filter to one month. Omit for all-time."},
            },
            "required": [],
        },
    },
    {
        "name": "get_category_breakdown",
        "description": "Get total spending per category (Groceries, Food & Dining, Transport, etc.).",
        "input_schema": {
            "type": "object",
            "properties": {
                "month": {"type": "string", "description": "Optional YYYY-MM to filter to one month. Omit for all-time."},
            },
            "required": [],
        },
    },
    {
        "name": "get_monthly_trend",
        "description": "Get income, expense, and net per month for the most recent N months, oldest first.",
        "input_schema": {
            "type": "object",
            "properties": {
                "months": {"type": "integer", "description": "How many recent months to return. Default 6."},
            },
            "required": [],
        },
    },
    {
        "name": "get_top_merchants",
        "description": "Get the counterparties/merchants with the highest total spend.",
        "input_schema": {
            "type": "object",
            "properties": {
                "month": {"type": "string", "description": "Optional YYYY-MM to filter to one month."},
                "limit": {"type": "integer", "description": "Max merchants to return. Default 10."},
            },
            "required": [],
        },
    },
    {
        "name": "flag_unusual_spending",
        "description": "Compare the two most recent months and flag categories that grew more than 40%, or are new.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "save_report_to_obsidian",
        "description": "Save the final advice report as a Markdown note. Call this ONCE at the end, after all analysis tools.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Report title, used as the filename."},
                "content": {"type": "string", "description": "Full Markdown report."},
            },
            "required": ["title", "content"],
        },
    },
]


def execute_tool(name: str, tool_input: dict) -> str:
    if name not in TOOLS:
        return f"Unknown tool: '{name}'. Available: {list(TOOLS.keys())}"
    try:
        return str(TOOLS[name](**tool_input))
    except Exception as exc:
        return f"Tool '{name}' raised: {exc}"
