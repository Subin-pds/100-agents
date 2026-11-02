"""Mock payment data for offline testing of classifier and recovery logic.

Allows the full agent pipeline to be tested without a live Razorpay account.
One mock payment per failure type — covers all 5 classifier branches.
"""
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))


def _ts(hours_ago: int = 1, hour_of_day: int | None = None) -> int:
    """Generate a Unix timestamp relative to now in IST."""
    now = datetime.now(IST)
    if hour_of_day is not None:
        now = now.replace(hour=hour_of_day, minute=30, second=0, microsecond=0)
    return int((now - timedelta(hours=hours_ago)).timestamp())


MOCK_PAYMENTS: list[dict] = [
    {
        # BANK_TECHNICAL: gateway 502 — transient, retry immediately
        "id": "pay_bank_001",
        "amount": 1500000,  # Rs.15,000 in paise
        "currency": "INR",
        "status": "failed",
        "method": "netbanking",
        "order_id": "order_001",
        "contact": "customer_001",
        "email": "customer001@example.com",
        "error_code": "GATEWAY_ERROR",
        "error_description": "Bank gateway returned HTTP 502 — temporary outage",
        "error_source": "bank",
        "created_at": _ts(hours_ago=2),
    },
    {
        # INSUFFICIENT_FUNDS: no balance — send payment link after 48hrs (payday)
        "id": "pay_insuf_001",
        "amount": 50000,  # Rs.500
        "currency": "INR",
        "status": "failed",
        "method": "card",
        "order_id": "order_002",
        "contact": "customer_002",
        "email": "customer002@example.com",
        "error_code": "BAD_REQUEST_ERROR",
        "error_description": "INSUFFICIENT_FUNDS in account",
        "error_source": "customer",
        "created_at": _ts(hours_ago=3),
    },
    {
        # CARD_EXPIRED: card on file expired — send new payment link immediately
        "id": "pay_card_exp_001",
        "amount": 299900,  # Rs.2,999
        "currency": "INR",
        "status": "failed",
        "method": "card",
        "order_id": "order_003",
        "contact": "customer_003",
        "email": "customer003@example.com",
        "error_code": "BAD_REQUEST_ERROR",
        "error_description": "EXPIRED card — card validity has passed",
        "error_source": "customer",
        "created_at": _ts(hours_ago=1),
    },
    {
        # UPI_TIMEOUT: deducted at bank, no confirmation — verify before acting
        "id": "pay_upi_001",
        "amount": 75000,  # Rs.750
        "currency": "INR",
        "status": "failed",
        "method": "upi",
        "order_id": "order_004",
        "contact": "customer_004",
        "email": "customer004@example.com",
        "error_code": "GATEWAY_ERROR",
        "error_description": "UPI transaction timed out — no confirmation received from bank",
        "error_source": "gateway",
        "created_at": _ts(hours_ago=1),
    },
    {
        # EVENING_PEAK: failed during 19:00–22:00 IST high traffic — delay retry
        "id": "pay_peak_001",
        "amount": 450000,  # Rs.4,500
        "currency": "INR",
        "status": "failed",
        "method": "card",
        "order_id": "order_005",
        "contact": "customer_005",
        "email": "customer005@example.com",
        "error_code": "GATEWAY_ERROR",
        "error_description": "Gateway timeout during peak traffic",
        "error_source": "gateway",
        "created_at": _ts(hours_ago=0, hour_of_day=20),  # 8:30 PM IST
    },
]


def get_mock_payments() -> list[dict]:
    """Return all mock payments for testing."""
    return MOCK_PAYMENTS


def get_mock_payment(payment_id: str) -> dict | None:
    """Fetch a single mock payment by ID."""
    return next((p for p in MOCK_PAYMENTS if p["id"] == payment_id), None)


def get_total_value_rupees() -> float:
    """Total value of all mock failed payments in rupees."""
    return sum(p["amount"] for p in MOCK_PAYMENTS) / 100
