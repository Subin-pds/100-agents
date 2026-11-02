"""Text-mode demo — runs the full pipeline on bundled sample data.

No real GPay export needed: ingests data/sample_takeout/MyActivity.html
(synthetic data) into a separate demo database, then runs the advisor.
Reports are saved under Finance/Agent7/Demo in Obsidian, kept apart from
any real financial data ingested via `python main.py ingest ...`.
"""

import os
import pathlib
import sys

from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")

DEMO_DB = pathlib.Path("data/demo_transactions.db")
os.environ["FINANCE_DB_PATH"] = str(DEMO_DB)

from agent import store  # noqa: E402  (import after env var set, tools.py reads it at import time)
from agent.advisor import FinanceAdvisor  # noqa: E402
from agent.ingest import parse_path  # noqa: E402
from agent.tools import FINANCE_NOTES_FOLDER  # noqa: E402


def main() -> None:
    load_dotenv()

    if DEMO_DB.exists():
        DEMO_DB.unlink()  # fresh run each time, no stale demo data

    source = pathlib.Path("data/sample_takeout/MyActivity.html")
    transactions = parse_path(source)
    print(f"Parsed {len(transactions)} sample transactions from {source}")

    inserted, skipped = store.insert_transactions(DEMO_DB, transactions)
    print(f"Stored {inserted} transaction(s) ({skipped} duplicates skipped)\n")

    import agent.tools as tools_module
    tools_module.FINANCE_NOTES_FOLDER = FINANCE_NOTES_FOLDER / "Demo"

    advisor = FinanceAdvisor()
    result = advisor.run(
        "Analyze my spending across July and August 2026 and give me financial advice."
    )
    print(f"\n{'='*60}\n{result}\n{'='*60}")


if __name__ == "__main__":
    main()
