"""Rule-based transaction categorization.

Keyword matching handles the bulk of transactions for free — an LLM call per
transaction would be slow and costly at hundreds of rows. Anything that
doesn't match falls into "Other" and is left for the advisor to reason about
in aggregate, rather than guessing category-by-category.
"""

import re

# Order matters: more specific categories are checked before generic ones
# (e.g. "swiggy instamart" should hit Groceries, not the broader Food match
# below it, if it were listed after).
CATEGORY_KEYWORDS: list[tuple[str, list[str]]] = [
    ("Income", [
        "salary", "credited by employer", "payroll", "refund", "cashback",
        "interest credited",
    ]),
    ("Rent", ["rent", "landlord", "housing.com", "nobroker"]),
    ("Utilities", [
        "electricity", "kseb", "water bill", "gas cylinder", "broadband",
        "airtel", "jio", "vi ", "bsnl", "postpaid", "prepaid recharge",
        "dth",
    ]),
    ("Groceries", [
        "grocery", "supermarket", "instamart", "blinkit", "zepto",
        "bigbasket", "dmart", "more supermarket", "reliance fresh",
    ]),
    ("Food & Dining", [
        "swiggy", "zomato", "restaurant", "cafe", "coffee", "hotel",
        "bakery", "food court",
    ]),
    ("Transport", [
        "uber", "ola", "rapido", "irctc", "indian railways", "metro",
        "fuel", "petrol", "diesel", "fastag", "parking",
    ]),
    ("Shopping", [
        "amazon", "flipkart", "myntra", "ajio", "meesho", "reliance digital",
        "croma",
    ]),
    ("Subscriptions", [
        "netflix", "spotify", "prime video", "youtube premium", "hotstar",
        "apple.com/bill", "google play", "playstore", "icloud",
    ]),
    ("Health", [
        "pharmacy", "hospital", "clinic", "apollo", "medplus", "diagnostic",
        "doctor",
    ]),
    ("Entertainment", ["bookmyshow", "pvr", "inox", "cinema"]),
    ("Investments", [
        "mutual fund", "zerodha", "groww", "upstox", "sip", "nps",
        "fixed deposit",
    ]),
]


def categorize(counterparty: str, raw_text: str) -> str:
    """Return a category name for a transaction based on keyword match."""
    haystack = f"{counterparty} {raw_text}".lower()
    for category, keywords in CATEGORY_KEYWORDS:
        for kw in keywords:
            if kw in haystack:
                return category
    # Bare peer-to-peer transfers (person name, no merchant keyword) are
    # common on GPay and worth their own bucket rather than "Other".
    if re.search(r"\b(sent|paid|received)\b", raw_text.lower()) and not any(
        c.isdigit() for c in counterparty
    ):
        return "Transfers"
    return "Other"
