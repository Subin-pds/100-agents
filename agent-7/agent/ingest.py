"""Parse transaction data out of a bank statement (PDF or CSV) or a Google
Takeout GPay export into a normalized list of transaction dicts.

PDF is the primary path for Indian bank apps (e.g. ICICI iMobile) that only
offer statements as PDF — tables are extracted directly rather than
regex-scraping raw PDF text. CSV covers banks/portals that do offer a
tabular export. Google Takeout HTML is a fallback for accounts where
Google Pay activity is actually present in Takeout (it generally isn't for
India, since GPay there runs on UPI rails outside standard Takeout data).

Each returned dict has: date (ISO), datetime (ISO or None), amount (float),
direction ("debit"/"credit"), counterparty (str), raw_text (str).
"""

import csv
import hashlib
import os
import re
from pathlib import Path

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from .categorize import categorize

# Matches the first line of a GPay activity block, e.g.:
#   "Paid ₹250.00 to Amit Kumar using Bank Account"
#   "Sent ₹500 to John Doe"
#   "Received ₹1,200.00 from Priya Nair"
#   "Paid ₹99 for Netflix subscription"
TX_PATTERNS = [
    (re.compile(r"^Paid\s+₹?([\d,]+\.?\d*)\s+to\s+(.+?)(?:\s+using\s+.+)?$", re.I), "debit"),
    (re.compile(r"^Sent\s+₹?([\d,]+\.?\d*)\s+to\s+(.+?)$", re.I), "debit"),
    (re.compile(r"^Paid\s+₹?([\d,]+\.?\d*)\s+for\s+(.+?)$", re.I), "debit"),
    (re.compile(r"^Received\s+₹?([\d,]+\.?\d*)\s+from\s+(.+?)$", re.I), "credit"),
    (re.compile(r"^Refunded?\s+₹?([\d,]+\.?\d*)\s+(?:from|by)\s+(.+?)$", re.I), "credit"),
]

# A trailing line like "Jan 5, 2026, 8:32:10 PM GMT+05:30" — strip the
# timezone abbreviation before handing off to dateutil, which chokes on
# "GMT+05:30" appended straight after a time.
DATE_LINE = re.compile(r"[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4},\s+\d{1,2}:\d{2}:\d{2}\s*[AP]M")


def _dedupe_key(dt: str, amount: float, counterparty: str, raw_text: str) -> str:
    payload = f"{dt}|{amount}|{counterparty}|{raw_text}".encode("utf-8")
    return hashlib.sha1(payload).hexdigest()


def _parse_block_text(text: str, source: str) -> dict | None:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return None

    description = lines[0]
    match = None
    direction = None
    for pattern, dirn in TX_PATTERNS:
        m = pattern.match(description)
        if m:
            match, direction = m, dirn
            break
    if not match:
        return None

    amount = float(match.group(1).replace(",", ""))
    counterparty = match.group(2).strip()

    dt_iso = None
    date_iso = None
    for ln in lines[1:]:
        dm = DATE_LINE.search(ln)
        if dm:
            try:
                parsed = dateparser.parse(dm.group(0))
                dt_iso = parsed.isoformat()
                date_iso = parsed.date().isoformat()
            except (ValueError, OverflowError):
                pass
            break

    category = categorize(counterparty, description)
    return {
        "date": date_iso,
        "datetime": dt_iso,
        "amount": amount,
        "direction": direction,
        "counterparty": counterparty,
        "category": category,
        "raw_text": description,
        "source_file": source,
        "dedupe_key": _dedupe_key(dt_iso or "", amount, counterparty, description),
    }


def parse_takeout_html(path: Path) -> list[dict]:
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
    transactions = []
    for cell in soup.select("div.content-cell") or soup.find_all("div"):
        text = cell.get_text(separator="\n")
        parsed = _parse_block_text(text, source=path.name)
        if parsed:
            transactions.append(parsed)
    return transactions


def _find_column(headers: list[str], substrings: list[str], exclude: list[str] | None = None) -> str | None:
    """Find a header matching any substring, skipping ones matching `exclude`.

    Bank statement headers vary a lot ("Debit Amount" vs "Withdrawal Amt."
    vs "Debit"), so columns are matched by substring rather than requiring
    an exact header name — this needs to work across HDFC/SBI/ICICI/Axis
    export formats (CSV or PDF table) without per-bank configuration.
    """
    exclude = exclude or []
    for header in headers:
        low = header.strip().lower()
        if any(x in low for x in exclude):
            continue
        if any(s in low for s in substrings):
            return header
    return None


def _tabular_rows_to_transactions(headers: list[str], rows: list[dict[str, str]], source_name: str) -> list[dict]:
    """Shared column-detection + row parsing for both CSV and PDF-table input."""
    date_col = _find_column(headers, ["date", "timestamp"], exclude=["value date", "value dat"])
    if not date_col:
        date_col = _find_column(headers, ["date", "timestamp"])
    desc_col = _find_column(headers, ["narration", "description", "particulars", "remarks", "details"])
    debit_col = _find_column(headers, ["debit", "withdrawal"])
    credit_col = _find_column(headers, ["credit", "deposit"])
    amount_col = _find_column(headers, ["amount", "value"], exclude=["debit", "credit", "withdrawal", "deposit"])

    transactions = []
    for row in rows:
        raw_amount = None
        direction = None
        if debit_col and row.get(debit_col):
            raw_amount, direction = row[debit_col], "debit"
        elif credit_col and row.get(credit_col):
            raw_amount, direction = row[credit_col], "credit"
        elif amount_col and row.get(amount_col):
            val = row[amount_col].replace(",", "").strip()
            try:
                fval = float(val)
                raw_amount, direction = str(abs(fval)), ("credit" if fval >= 0 else "debit")
            except ValueError:
                pass

        if not raw_amount:
            continue
        try:
            amount = float(str(raw_amount).replace(",", "").strip() or 0)
        except ValueError:
            continue
        if amount == 0:
            continue

        description = (row.get(desc_col) or "").strip() if desc_col else "Transaction"
        date_raw = (row.get(date_col) or "").strip() if date_col else ""
        date_iso, dt_iso = None, None
        if date_raw:
            try:
                parsed = dateparser.parse(date_raw, dayfirst=True)
                date_iso = parsed.date().isoformat()
                dt_iso = parsed.isoformat()
            except (ValueError, OverflowError):
                pass

        category = categorize(description, description)
        transactions.append({
            "date": date_iso,
            "datetime": dt_iso,
            "amount": amount,
            "direction": direction,
            "counterparty": description,
            "category": category,
            "raw_text": description,
            "source_file": source_name,
            "dedupe_key": _dedupe_key(dt_iso or "", amount, description, description),
        })
    return transactions


def parse_csv_statement(path: Path) -> list[dict]:
    """Parse a bank/GPay statement exported as CSV."""
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return []
        headers = list(reader.fieldnames)
        rows = list(reader)
    return _tabular_rows_to_transactions(headers, rows, path.name)


def parse_pdf_statement(path: Path, password: str | None = None) -> list[dict]:
    """Parse a bank statement PDF (e.g. ICICI iMobile) by extracting tables.

    Statement PDFs typically render one table per page with a repeated
    header row (Value Date / Transaction Date / Remarks / Withdrawal /
    Deposit / Balance). Each page's table is converted independently since
    a header can repeat or shift slightly page to page; rows that don't
    resolve to a valid amount (page totals, disclaimers, blank rows) are
    silently skipped by _tabular_rows_to_transactions.

    Most Indian bank statement PDFs are password-protected (often PAN or a
    bank-specific scheme like name+DOB) — pass `password` or set
    STATEMENT_PDF_PASSWORD so pdfplumber can open it.
    """
    import pdfplumber

    password = password or os.getenv("STATEMENT_PDF_PASSWORD")

    try:
        pdf_ctx = pdfplumber.open(path, password=password)
    except Exception as exc:
        # pdfplumber wraps pdfminer's PDFPasswordIncorrect in a bare
        # PdfminerException whose str() is empty — the real signal is the
        # wrapped exception's class name, not its (missing) message.
        cause_name = type(exc.args[0]).__name__ if exc.args else ""
        haystack = f"{exc} {cause_name}".lower()
        if "password" in haystack or "encrypt" in haystack:
            raise ValueError(
                f"{path.name} is password-protected"
                + (" (wrong password)" if password else "")
                + ". Pass --pdf-password or set STATEMENT_PDF_PASSWORD in .env."
            ) from exc
        raise

    transactions = []
    with pdf_ctx as pdf:
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                if not table or len(table) < 2:
                    continue
                headers = [(h or "").strip() for h in table[0]]
                if not any(headers):
                    continue
                rows = [
                    {headers[i]: (cell or "") for i, cell in enumerate(row) if i < len(headers)}
                    for row in table[1:]
                ]
                transactions.extend(_tabular_rows_to_transactions(headers, rows, path.name))
    return transactions


def parse_source(path: Path, password: str | None = None) -> list[dict]:
    """Parse a single file, dispatching on extension."""
    if path.suffix.lower() in (".html", ".htm"):
        return parse_takeout_html(path)
    if path.suffix.lower() == ".csv":
        return parse_csv_statement(path)
    if path.suffix.lower() == ".pdf":
        return parse_pdf_statement(path, password=password)
    return []


def parse_path(path: Path, password: str | None = None) -> list[dict]:
    """Parse a file or every supported file in a directory (recursively)."""
    if path.is_file():
        return parse_source(path, password=password)
    transactions = []
    for pattern in ("*.html", "*.htm", "*.csv", "*.pdf"):
        for file in path.rglob(pattern):
            transactions.extend(parse_source(file, password=password))
    return transactions
