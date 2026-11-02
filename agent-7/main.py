"""Entry point for Agent 7 — Personal Finance Tracker.

Usage:
    python main.py ingest <path-to-statement.pdf-or-.csv-or-folder> [--pdf-password PASS]
    python main.py summary [--month YYYY-MM]
    python main.py advise [--month YYYY-MM]
"""

import argparse
import os
import pathlib
import sys

from dotenv import load_dotenv

# Windows consoles often default to cp1252, which can't print the rupee
# sign used throughout reports — force UTF-8 stdout before anything prints.
sys.stdout.reconfigure(encoding="utf-8")

from agent import store
from agent.advisor import FinanceAdvisor
from agent.ingest import parse_path

DB_PATH = pathlib.Path(os.getenv("FINANCE_DB_PATH", "data/transactions.db"))


def cmd_ingest(args: argparse.Namespace) -> None:
    source = pathlib.Path(args.source)
    if not source.exists():
        sys.exit(f"Path not found: {source}")

    try:
        transactions = parse_path(source, password=args.pdf_password)
    except ValueError as exc:
        sys.exit(str(exc))

    if not transactions:
        sys.exit(
            "No transactions parsed. Expected a bank statement .pdf or .csv, "
            "a Google Takeout 'My Activity' .html file, or a folder containing them."
        )

    inserted, skipped = store.insert_transactions(DB_PATH, transactions)
    print(f"Parsed {len(transactions)} transaction(s): {inserted} new, {skipped} already stored.")


def cmd_summary(args: argparse.Namespace) -> None:
    stats = store.summary_stats(DB_PATH, args.month)
    print(f"Income:  Rs {stats['income']:,.2f}")
    print(f"Expense: Rs {stats['expense']:,.2f}")
    print(f"Net:     Rs {stats['net']:,.2f}")
    print(f"Transactions: {stats['transaction_count']}")


def cmd_advise(args: argparse.Namespace) -> None:
    query = "Analyze my spending and give me financial advice."
    if args.month:
        query += f" Focus on {args.month}."
    advisor = FinanceAdvisor()
    result = advisor.run(query)
    print(f"\n{'='*60}\n{result}\n{'='*60}")


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Agent 7 — Personal Finance Tracker")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", help="Parse and store a bank statement (PDF/CSV) or Takeout export")
    p_ingest.add_argument("source", help="File or folder to parse")
    p_ingest.add_argument(
        "--pdf-password", default=None,
        help="Password for an encrypted statement PDF (or set STATEMENT_PDF_PASSWORD in .env)",
    )
    p_ingest.set_defaults(func=cmd_ingest)

    p_summary = sub.add_parser("summary", help="Print quick totals (no LLM call)")
    p_summary.add_argument("--month", default=None, help="Filter to YYYY-MM")
    p_summary.set_defaults(func=cmd_summary)

    p_advise = sub.add_parser("advise", help="Run the financial advisor agent")
    p_advise.add_argument("--month", default=None, help="Focus advice on YYYY-MM")
    p_advise.set_defaults(func=cmd_advise)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
