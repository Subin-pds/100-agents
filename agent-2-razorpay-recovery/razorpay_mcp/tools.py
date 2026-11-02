"""Typed wrappers for Razorpay MCP tool calls with exponential backoff retry.

Wrappers decouple the agent from the raw MCP API — if Razorpay changes a
tool signature, you fix it here in one place, not across every caller.
"""
import asyncio
import json
import os
import random
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog

from razorpay_mcp.client import RazorpayMCPClient, RazorpayMCPError

logger = structlog.get_logger()

_MAX_ATTEMPTS = int(os.environ.get("MAX_RETRY_ATTEMPTS", "3"))


async def call_with_retry(
    client: RazorpayMCPClient,
    tool_name: str,
    args: dict[str, Any],
    max_attempts: int = _MAX_ATTEMPTS,
) -> Any:
    """Call a Razorpay MCP tool with exponential backoff + jitter.

    Non-retryable errors — the problem is in the request, not timing:
      401 — bad credentials
      400 — malformed request

    Retryable — transient issues that may resolve on their own:
      5xx server errors, network timeouts

    Jitter (random.uniform) prevents retry storms where all clients hit
    the server simultaneously after a shared outage.
    """
    for attempt in range(max_attempts):
        try:
            return await client.call_tool(tool_name, args)
        except RazorpayMCPError as e:
            if e.status in (401, 400):
                raise
            if attempt == max_attempts - 1:
                logger.error("tool_max_retries_exceeded", tool=tool_name, attempts=max_attempts)
                raise
            wait = (2 ** attempt) + random.uniform(0, 1)
            logger.warning(
                "tool_retry",
                tool=tool_name,
                attempt=attempt + 1,
                wait_seconds=round(wait, 2),
                error=str(e),
            )
            await asyncio.sleep(wait)


def _parse_content(result: Any) -> dict[str, Any] | list[Any]:
    """Extract JSON payload from an MCP CallToolResult."""
    if hasattr(result, "content") and result.content:
        raw = result.content[0]
        if hasattr(raw, "text"):
            return json.loads(raw.text)
    return {}


async def fetch_failed_payments(
    client: RazorpayMCPClient,
    lookback_hours: int = 24,
    count: int = 100,
) -> list[dict[str, Any]]:
    """Fetch all failed payments within the lookback window.

    Bounded by a time window to avoid fetching stale historical data and
    hitting rate limits with unbounded queries.
    """
    now = datetime.now(timezone.utc)
    from_ts = int((now - timedelta(hours=lookback_hours)).timestamp())
    to_ts = int(now.timestamp())

    result = await call_with_retry(client, "fetch_all_payments", {
        "from": from_ts,
        "to": to_ts,
        "count": count,
    })

    data = _parse_content(result)
    items: list[dict] = data.get("items", data.get("payments", [])) if isinstance(data, dict) else data  # type: ignore[assignment]
    failed = [p for p in items if p.get("status") == "failed"]

    logger.info(
        "fetch_failed_payments",
        total_fetched=len(items),
        failed_count=len(failed),
        lookback_hours=lookback_hours,
    )
    return failed


async def fetch_payment_detail(
    client: RazorpayMCPClient,
    payment_id: str,
) -> dict[str, Any]:
    """Fetch full payment details including current status and error codes.

    Always call this before any mutation (capture, refund) to verify the
    current state. Mutating without reading first is how double-charges happen.
    """
    result = await call_with_retry(client, "fetch_payment", {"payment_id": payment_id})
    data = _parse_content(result)
    return data if isinstance(data, dict) else {}


async def create_and_send_payment_link(
    client: RazorpayMCPClient,
    amount: int,
    description: str,
    customer_contact: str = "",
    customer_email: str = "",
) -> dict[str, Any]:
    """Create a Razorpay payment link and send it via SMS/email.

    Creation and sending are two separate tool calls so that if SMS delivery
    fails, we can retry just the send step without creating a duplicate link.
    """
    link_args: dict[str, Any] = {
        "amount": amount,
        "currency": "INR",
        "description": description,
    }
    customer: dict[str, str] = {}
    if customer_contact:
        customer["contact"] = customer_contact
    if customer_email:
        customer["email"] = customer_email
    if customer:
        link_args["customer"] = customer

    link_result = await call_with_retry(client, "create_payment_link", link_args)
    link_data = _parse_content(link_result)
    link_id = link_data.get("id", "") if isinstance(link_data, dict) else ""

    if link_id:
        await call_with_retry(client, "send_payment_link", {"payment_link_id": link_id})
        logger.info("payment_link_sent", link_id=link_id, amount_paise=amount)

    return link_data if isinstance(link_data, dict) else {}


async def capture_authorized_payment(
    client: RazorpayMCPClient,
    payment_id: str,
    amount: int,
) -> dict[str, Any]:
    """Capture a payment confirmed to be in 'authorized' state.

    Callers must call fetch_payment_detail first and verify status == 'authorized'
    before calling this. The safety check is intentionally kept in the caller
    so it's visible in the calling code, not hidden inside this wrapper.
    """
    result = await call_with_retry(client, "capture_payment", {
        "payment_id": payment_id,
        "amount": amount,
    })
    data = _parse_content(result)
    logger.info("payment_captured", payment_id=payment_id, amount_paise=amount)
    return data if isinstance(data, dict) else {}
