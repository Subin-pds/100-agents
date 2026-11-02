"""Scripted demo for LinkedIn screen recording.

Clean output + deliberate pauses so every step is readable on video.
No extra dependencies — uses ANSI colour codes only.

Usage:
    python demo_video.py

Record with Win+G (Xbox Game Bar) or OBS. Target: 60-90 seconds.
"""
import asyncio
import os
import time
import sys

from dotenv import load_dotenv
from agent.classifier import PaymentClassifier
from agent.recovery import RecoveryAgent, RecoveryResult
from agent.reporter import RecoveryReporter
from tests.mock_payments import MOCK_PAYMENTS, get_total_value_rupees

load_dotenv()

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

# ── ANSI colours ────────────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RED    = "\033[91m"
DIM    = "\033[2m"
WHITE  = "\033[97m"

def c(colour: str, text: str) -> str:
    return f"{colour}{text}{RESET}"

def line(ch: str = "─", width: int = 62) -> str:
    return ch * width

def pause(seconds: float = 1.5) -> None:
    time.sleep(seconds)

def print_slow(text: str, delay: float = 0.03) -> None:
    """Print character-by-character for a typing effect."""
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(delay)
    print()


# ── Failure type colours ─────────────────────────────────────────────────────
FAILURE_COLOUR = {
    "bank_technical":     YELLOW,
    "insufficient_funds": RED,
    "card_expired":       RED,
    "upi_timeout":        CYAN,
    "evening_peak":       YELLOW,
}

ACTION_COLOUR = {
    "retry_immediately":    GREEN,
    "schedule_reminder_48h": YELLOW,
    "send_payment_link":    GREEN,
    "payment_link_created": GREEN,
    "verify_upi_status":    CYAN,
    "schedule_post_peak":   YELLOW,
}


async def run() -> None:
    os.system("cls" if os.name == "nt" else "clear")

    # ── TITLE ────────────────────────────────────────────────────────────────
    print()
    print(c(BOLD + CYAN, line("═")))
    print(c(BOLD + WHITE, "  RAZORPAY FAILED PAYMENT RECOVERY AGENT"))
    print(c(DIM,          "  Agent 2 of 100 | Built with Claude Sonnet + MCP"))
    print(c(BOLD + CYAN,  line("═")))
    print()
    pause(2.0)

    total = get_total_value_rupees()
    print_slow(c(BOLD, f"  {len(MOCK_PAYMENTS)} failed payments detected  |  ") +
               c(RED + BOLD, f"Rs.{total:,.0f} at risk"), delay=0.02)
    print()
    pause(2.5)

    # ── STEP 1: CLASSIFY ─────────────────────────────────────────────────────
    print(c(BOLD + CYAN, line()))
    print(c(BOLD, "  STEP 1 / 3   Classifying failures with Claude Sonnet 4"))
    print(c(BOLD + CYAN, line()))
    print()
    pause(1.0)

    classifier = PaymentClassifier()
    classified = classifier.classify_batch(MOCK_PAYMENTS)

    headers = f"  {'Payment ID':<22} {'Failure Type':<22} {'Amount':>9}  {'Confidence':>10}  {'Priority':>8}"
    print(c(DIM, headers))
    print(c(DIM, "  " + line("─", 58)))
    pause(0.5)

    for cp in classified:
        ftype = cp.failure_type.value
        fcolour = FAILURE_COLOUR.get(ftype, WHITE)
        row = (
            f"  {cp.payment_id:<22} "
            + c(fcolour + BOLD, f"{ftype:<22}")
            + f" Rs.{cp.amount // 100:>6,}"
            + f"  {cp.recovery_probability:>9.0%}"
            + f"  {cp.priority_score:>8,.0f}"
        )
        print(row)
        pause(0.6)

    print()
    pause(1.5)

    # ── STEP 2: RECOVER ──────────────────────────────────────────────────────
    print(c(BOLD + CYAN, line()))
    print(c(BOLD, "  STEP 2 / 3   Executing recovery strategies  ") +
          c(YELLOW + BOLD, "(DRY_RUN=true — safe mode)"))
    print(c(BOLD + CYAN, line()))
    print()
    pause(1.0)

    class _MockMCPClient:
        async def call_tool(self, name, args):
            pass

    agent = RecoveryAgent(_MockMCPClient())  # type: ignore[arg-type]
    results: list[RecoveryResult] = []

    for payment in classified:
        result = await agent.recover(payment)
        results.append(result)

        status_str = c(GREEN + BOLD, " ✓ ") if result.success else c(RED + BOLD, " ✗ ")
        action_col = ACTION_COLOUR.get(result.action_taken, WHITE)
        action_str = c(action_col + BOLD, f"{result.action_taken:<30}")

        print(f" {status_str} {result.payment_id:<22} {action_str}")
        print(c(DIM, f"       └─ {result.detail}"))
        pause(0.8)

    print()

    # ── UPI CALLOUT ──────────────────────────────────────────────────────────
    pause(1.0)
    print(c(YELLOW + BOLD, "  ⚠  UPI SAFETY GUARD"))
    print(c(DIM, "     pay_upi_001 → status verified BEFORE any capture"))
    print(c(DIM, "     Prevents double-charge when bank deducted but gateway timed out"))
    print()
    pause(2.0)

    # ── STEP 3: REPORT ───────────────────────────────────────────────────────
    print(c(BOLD + CYAN, line()))
    print(c(BOLD, "  STEP 3 / 3   Generating recovery report with Claude Sonnet 4"))
    print(c(BOLD + CYAN, line()))
    print()
    pause(1.0)

    reporter = RecoveryReporter()
    report = reporter.generate(classified, results)
    print(report)

    # ── FOOTER ───────────────────────────────────────────────────────────────
    print(c(BOLD + CYAN, line("═")))
    recovered = sum(1 for r in results if r.success)
    total_recovered = sum(
        c_.amount for c_, r in zip(classified, results) if r.success
    )
    print(c(GREEN + BOLD, f"  {recovered}/{len(results)} payments actioned  |  "
                           f"Rs.{total_recovered // 100:,} recovery initiated"))
    print(c(DIM,   "  github.com/subinpds  |  #GenAI #BuildingInPublic #100Agents"))
    print(c(BOLD + CYAN, line("═")))
    print()


if __name__ == "__main__":
    asyncio.run(run())
