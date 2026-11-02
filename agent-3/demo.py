# CCA-F Domain1: Agentic loop — full booking loop without Twilio; type Malayalam in terminal
# CCA-F Domain4: Prompt engineering — demonstrates Malayalam structured output from Claude
# INTERVIEW: demo.py lets you test the full agent locally before wiring up Twilio

"""Text-mode demo — no phone, no Twilio, no microphone needed.

Type Malayalam (or transliterated English) and the agent responds.
Run:
    python demo.py
"""

import os
import sys
from datetime import date, time

# Force UTF-8 output on Windows so Malayalam renders correctly
if sys.platform == "win32":
    import ctypes
    ctypes.windll.kernel32.SetConsoleOutputCP(65001)  # type: ignore[attr-defined]

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

from dotenv import load_dotenv

load_dotenv()

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

import time as _time

RESET = "\033[0m"
BOLD  = "\033[1m"
CYAN  = "\033[96m"
GREEN = "\033[92m"
DIM   = "\033[2m"
YELLOW= "\033[93m"


def c(colour: str, text: str) -> str:
    return f"{colour}{text}{RESET}"


def main() -> None:
    from agent.booking import process_turn
    from agent.calendar import get_calendar

    cal = get_calendar()

    print()
    print(c(BOLD + CYAN, "═" * 62))
    print(c(BOLD, "  MARSAGENT — MALAYALAM CLINIC BOOKING ASSISTANT"))
    print(c(DIM,  "  Agent 3 of 100 | Claude Sonnet 4 + Whisper + gTTS"))
    print(c(BOLD + CYAN, "═" * 62))
    print()
    print(c(DIM, "  Type in Malayalam or transliterated English."))
    print(c(DIM, '  Example: "ഡോക്ടർ ആനന്ദിനെ നാളെ രാവിലെ 10 മണിക്ക് കാണണം"'))
    print(c(DIM, "  Type 'quit' to exit."))
    print()

    history = []
    greeting = "നമസ്കാരം! ഇത് MarsAgent ക്ലിനിക്ക് ആണ്. ഡോക്ടറുടെ അപ്പോയ്ൻ്റ്മെൻ്റ് ബുക്ക് ചെയ്യാൻ ഞാൻ സഹായിക്കാം. നിങ്ങളുടെ പേര്, ഡോക്ടർ, തീയതി, സമയം പറയൂ."
    print(c(GREEN + BOLD, f"  🤖 Agent: ") + greeting)
    print()

    while True:
        try:
            user_input = input(c(CYAN + BOLD, "  You: ") + RESET).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Exiting.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "bye"):
            print(c(DIM, "  Goodbye!"))
            break

        reply, intent = process_turn(history, user_input)

        print()
        print(c(GREEN + BOLD, "  🤖 Agent: ") + reply)

        if intent:
            print()
            print(c(BOLD + CYAN, "  " + "─" * 58))
            print(c(BOLD, "  INTENT EXTRACTED"))
            print(c(DIM,  f"    Patient : {intent.get('patient_name')}"))
            print(c(DIM,  f"    Doctor  : {intent.get('doctor')}"))
            print(c(DIM,  f"    Date    : {intent.get('date')}"))
            print(c(DIM,  f"    Time    : {intent.get('time_hour')}:00"))
            print(c(BOLD + CYAN, "  " + "─" * 58))
            print()

            slot = cal.book(
                doctor=intent["doctor"],
                on_date=date.fromisoformat(intent["date"]),
                at_time=time(int(intent["time_hour"]), 0),
                patient=intent["patient_name"],
            )

            if slot:
                confirmation = cal.confirmation_message(slot)
                print(c(GREEN + BOLD, "  ✓ BOOKED: ") + confirmation)
                print()
                print(c(BOLD + CYAN, "═" * 62))
                print(c(GREEN + BOLD, f"  Confirmation: {slot.confirmation}"))
                print(c(BOLD + CYAN, "═" * 62))
            else:
                print(c(YELLOW + BOLD, "  ⚠  Slot not available. Ask for another time."))

            print()
            again = input(c(DIM, "  Book another? (y/n): ")).strip().lower()
            if again == "y":
                history = []
                print()
                print(c(GREEN + BOLD, "  🤖 Agent: ") + greeting)
                print()
            else:
                break

        print()


if __name__ == "__main__":
    main()
