"""Creates test payment links via Razorpay MCP so we can simulate failures.

Run this script, open each link in your browser, and pay with the
test cards listed below to generate different failure types.
Then run `python main.py` to see the agent recover them.

Razorpay test cards:
  CARD_EXPIRED      → any card number, expiry in the past (e.g. 01/20)
  INSUFFICIENT_FUNDS→ 4000 0000 0000 9995
  BANK_TECHNICAL    → 4000 0000 0000 0002  (generic decline / gateway error)
  SUCCESS (control) → 4111 1111 1111 1111, expiry any future date
  CVV: any 3 digits for all cards
  OTP: 1234 (Razorpay test OTP)
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv

load_dotenv()

from razorpay_mcp.client import get_client
from razorpay_mcp.tools import call_with_retry


TEST_PAYMENTS = [
    {"amount": 1500000, "description": "Order #001 — ₹15,000 laptop purchase",   "card_hint": "Use card 4000 0000 0000 0002 → triggers BANK_TECHNICAL"},
    {"amount": 50000,   "description": "Order #002 — ₹500 subscription renewal", "card_hint": "Use any card with past expiry (e.g. 01/20) → triggers CARD_EXPIRED"},
    {"amount": 299900,  "description": "Order #003 — ₹2,999 annual plan",         "card_hint": "Use card 4000 0000 0000 9995 → triggers INSUFFICIENT_FUNDS"},
    {"amount": 75000,   "description": "Order #004 — ₹750 course payment",        "card_hint": "UPI ID: failure@razorpay → triggers UPI_TIMEOUT"},
]


async def main() -> None:
    print("\nCreating Razorpay test payment links...\n")

    async with get_client() as client:
        for i, p in enumerate(TEST_PAYMENTS, 1):
            try:
                result = await call_with_retry(client, "create_payment_link", {
                    "amount": p["amount"],
                    "currency": "INR",
                    "description": p["description"],
                })

                import json
                url = "— check Razorpay dashboard"
                if hasattr(result, "content") and result.content:
                    raw = result.content[0]
                    text = getattr(raw, "text", "") or ""
                    if text.strip():
                        data = json.loads(text)
                        url = data.get("short_url", data.get("id", url))

                print(f"  Payment {i}: {p['description']}")
                print(f"  URL    : {url}")
                print(f"  Card   : {p['card_hint']}")
                print()

            except Exception as e:
                print(f"  Payment {i}: FAILED to create — {e}\n")

            await asyncio.sleep(1)  # avoid rate limiting

    print("Steps:")
    print("  1. Open each URL in your browser")
    print("  2. Pay using the card listed (OTP = 1234 for all)")
    print("  3. The payments will fail — that's expected!")
    print("  4. Run `python main.py` to see the agent classify and recover them\n")


if __name__ == "__main__":
    asyncio.run(main())
