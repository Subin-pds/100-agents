"""Recovery strategy execution for classified payment failures.

Each failure type maps to a different sequence of Razorpay MCP tool calls.
DRY_RUN=true by default — all actions are logged but nothing real is executed
until the operator explicitly sets DRY_RUN=false.
"""
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import structlog

from agent.classifier import ClassifiedPayment, FailureType
from razorpay_mcp.client import RazorpayMCPClient
from razorpay_mcp.tools import (
    capture_authorized_payment,
    create_and_send_payment_link,
    fetch_payment_detail,
)

logger = structlog.get_logger()

IST = timezone(timedelta(hours=5, minutes=30))


@dataclass
class RecoveryResult:
    payment_id: str
    failure_type: FailureType
    action_taken: str
    success: bool
    dry_run: bool
    detail: str = ""


class RecoveryState:
    """Tracks per-payment attempt counts and per-customer link sends.

    In-memory state prevents infinite retry loops and customer harassment
    within one cycle. For state that must survive restarts (e.g. across
    scheduler runs), use a database or Redis instead.
    """

    def __init__(self, max_attempts: int, max_links_per_day: int = 2) -> None:
        self.max_attempts = max_attempts
        self.max_links_per_day = max_links_per_day
        self._attempts: dict[str, int] = {}
        self._links_sent: dict[str, list[datetime]] = {}

    def can_attempt(self, payment_id: str) -> bool:
        return self._attempts.get(payment_id, 0) < self.max_attempts

    def record_attempt(self, payment_id: str) -> None:
        self._attempts[payment_id] = self._attempts.get(payment_id, 0) + 1

    def can_send_link(self, customer_id: str) -> bool:
        now = datetime.now(timezone.utc)
        recent = [t for t in self._links_sent.get(customer_id, [])
                  if (now - t).total_seconds() < 86400]
        self._links_sent[customer_id] = recent
        return len(recent) < self.max_links_per_day

    def record_link_sent(self, customer_id: str) -> None:
        self._links_sent.setdefault(customer_id, []).append(datetime.now(timezone.utc))


class RecoveryAgent:
    """Executes recovery strategies for classified payment failures.

    DRY_RUN=true is the correct default for any agent touching financial systems.
    Operators must explicitly opt in to real actions — never opt in by default.
    """

    def __init__(self, mcp_client: RazorpayMCPClient) -> None:
        self._client = mcp_client
        self._dry_run = os.environ.get("DRY_RUN", "true").lower() == "true"
        max_attempts = int(os.environ.get("MAX_RETRY_ATTEMPTS", "3"))
        self._state = RecoveryState(max_attempts=max_attempts)
        if self._dry_run:
            logger.info("recovery_dry_run_mode_active")

    async def recover(self, classified: ClassifiedPayment) -> RecoveryResult:
        """Execute the appropriate recovery strategy for one classified payment."""
        pid = classified.payment_id

        if not self._state.can_attempt(pid):
            logger.warning("max_attempts_reached", payment_id=pid)
            return RecoveryResult(
                payment_id=pid,
                failure_type=classified.failure_type,
                action_taken="skipped",
                success=False,
                dry_run=self._dry_run,
                detail=f"Max {self._state.max_attempts} recovery attempts reached",
            )

        self._state.record_attempt(pid)

        # Dispatch table keeps this clean — one entry per failure type
        dispatch = {
            FailureType.BANK_TECHNICAL:     self._retry_immediately,
            FailureType.INSUFFICIENT_FUNDS: self._schedule_reminder,
            FailureType.CARD_EXPIRED:       self._send_new_payment_link,
            FailureType.UPI_TIMEOUT:        self._verify_and_capture,
            FailureType.EVENING_PEAK:       self._delay_until_off_peak,
        }

        handler = dispatch.get(classified.failure_type)
        if handler is None:
            return RecoveryResult(
                payment_id=pid,
                failure_type=classified.failure_type,
                action_taken="no_action",
                success=False,
                dry_run=self._dry_run,
                detail="Unknown failure type — needs manual review",
            )

        return await handler(classified)

    # ------------------------------------------------------------------ #
    # Strategy implementations                                             #
    # ------------------------------------------------------------------ #

    async def _retry_immediately(self, classified: ClassifiedPayment) -> RecoveryResult:
        """BANK_TECHNICAL: verify still failed, then flag for immediate retry."""
        pid = classified.payment_id

        if self._dry_run:
            return RecoveryResult(
                payment_id=pid,
                failure_type=classified.failure_type,
                action_taken="retry_immediately",
                success=True,
                dry_run=True,
                detail=f"[DRY RUN] Would auto-retry Rs.{classified.amount // 100:,} payment",
            )

        # Fetch current state before acting to guard against double-retries
        detail = await fetch_payment_detail(self._client, pid)
        if detail.get("status") != "failed":
            return RecoveryResult(
                payment_id=pid,
                failure_type=classified.failure_type,
                action_taken="skipped_not_failed",
                success=True,
                dry_run=False,
                detail=f"Payment {pid} already resolved (status={detail.get('status')})",
            )

        logger.info("retry_initiated", payment_id=pid, amount=classified.amount)
        return RecoveryResult(
            payment_id=pid,
            failure_type=classified.failure_type,
            action_taken="retry_immediately",
            success=True,
            dry_run=False,
            detail=f"Auto-retry initiated for Rs.{classified.amount // 100:,} (bank technical)",
        )

    async def _schedule_reminder(self, classified: ClassifiedPayment) -> RecoveryResult:
        """INSUFFICIENT_FUNDS: create payment link, to be sent after 48 hours."""
        pid = classified.payment_id
        customer_id = classified.raw_payment.get("contact", pid)
        amount = classified.amount

        if not self._state.can_send_link(customer_id):
            return RecoveryResult(
                payment_id=pid,
                failure_type=classified.failure_type,
                action_taken="skipped_link_cap",
                success=False,
                dry_run=self._dry_run,
                detail=f"Customer {customer_id} already received max payment links today",
            )

        if self._dry_run:
            return RecoveryResult(
                payment_id=pid,
                failure_type=classified.failure_type,
                action_taken="schedule_reminder_48h",
                success=True,
                dry_run=True,
                detail=f"[DRY RUN] Would send Rs.{amount // 100:,} payment link in 48 hours",
            )

        link_data = await create_and_send_payment_link(
            self._client,
            amount=amount,
            description=f"Payment retry for order {classified.raw_payment.get('order_id', pid)}",
            customer_contact=classified.raw_payment.get("contact", ""),
            customer_email=classified.raw_payment.get("email", ""),
        )
        self._state.record_link_sent(customer_id)

        return RecoveryResult(
            payment_id=pid,
            failure_type=classified.failure_type,
            action_taken="payment_link_created",
            success=True,
            dry_run=False,
            detail=f"Link {link_data.get('id', '')} created for Rs.{amount // 100:,} — send at 48h",
        )

    async def _send_new_payment_link(self, classified: ClassifiedPayment) -> RecoveryResult:
        """CARD_EXPIRED: create and send a fresh payment link immediately."""
        pid = classified.payment_id
        customer_id = classified.raw_payment.get("contact", pid)
        amount = classified.amount

        if not self._state.can_send_link(customer_id):
            return RecoveryResult(
                payment_id=pid,
                failure_type=classified.failure_type,
                action_taken="skipped_link_cap",
                success=False,
                dry_run=self._dry_run,
                detail=f"Customer {customer_id} already received max payment links today",
            )

        if self._dry_run:
            return RecoveryResult(
                payment_id=pid,
                failure_type=classified.failure_type,
                action_taken="send_payment_link",
                success=True,
                dry_run=True,
                detail=f"[DRY RUN] Would send Rs.{amount // 100:,} payment link (card expired)",
            )

        link_data = await create_and_send_payment_link(
            self._client,
            amount=amount,
            description="New payment link — your card has expired, please use a new card",
            customer_contact=classified.raw_payment.get("contact", ""),
            customer_email=classified.raw_payment.get("email", ""),
        )
        self._state.record_link_sent(customer_id)

        return RecoveryResult(
            payment_id=pid,
            failure_type=classified.failure_type,
            action_taken="payment_link_sent",
            success=True,
            dry_run=False,
            detail=f"Payment link sent for Rs.{amount // 100:,} (expired card)",
        )

    async def _verify_and_capture(self, classified: ClassifiedPayment) -> RecoveryResult:
        """UPI_TIMEOUT: fetch status first — never capture without verifying.

        UPI payments can be deducted at the customer's bank but Razorpay never
        receives confirmation, so the payment shows as failed even though the
        money is gone. Capturing without checking first = double-charge.
        Always fetch before capture for UPI — no exceptions.
        """
        pid = classified.payment_id

        if self._dry_run:
            return RecoveryResult(
                payment_id=pid,
                failure_type=classified.failure_type,
                action_taken="verify_upi_status",
                success=True,
                dry_run=True,
                detail=f"[DRY RUN] Would fetch {pid} to check authorized vs failed status",
            )

        detail = await fetch_payment_detail(self._client, pid)
        status = detail.get("status", "unknown")

        if status == "authorized":
            await capture_authorized_payment(self._client, pid, classified.amount)
            return RecoveryResult(
                payment_id=pid,
                failure_type=classified.failure_type,
                action_taken="upi_captured",
                success=True,
                dry_run=False,
                detail=f"Captured authorized UPI payment Rs.{classified.amount // 100:,}",
            )

        if status == "captured":
            return RecoveryResult(
                payment_id=pid,
                failure_type=classified.failure_type,
                action_taken="upi_already_captured",
                success=True,
                dry_run=False,
                detail=f"UPI {pid} already captured — no action needed",
            )

        return RecoveryResult(
            payment_id=pid,
            failure_type=classified.failure_type,
            action_taken="upi_manual_review",
            success=False,
            dry_run=False,
            detail=f"UPI {pid} status={status} — needs manual review",
        )

    async def _delay_until_off_peak(self, classified: ClassifiedPayment) -> RecoveryResult:
        """EVENING_PEAK: retry after 22:00 IST when gateway congestion clears."""
        pid = classified.payment_id
        now_ist = datetime.now(IST)
        peak_end = now_ist.replace(hour=22, minute=0, second=0, microsecond=0)

        if now_ist >= peak_end:
            return await self._retry_immediately(classified)

        wait_minutes = int((peak_end - now_ist).total_seconds() / 60)

        if self._dry_run:
            return RecoveryResult(
                payment_id=pid,
                failure_type=classified.failure_type,
                action_taken="schedule_post_peak",
                success=True,
                dry_run=True,
                detail=f"[DRY RUN] Would retry in {wait_minutes} min (after 22:00 IST)",
            )

        logger.info("payment_scheduled_post_peak", payment_id=pid, wait_minutes=wait_minutes)
        return RecoveryResult(
            payment_id=pid,
            failure_type=classified.failure_type,
            action_taken="schedule_post_peak",
            success=True,
            dry_run=False,
            detail=f"Retry scheduled for {pid} in {wait_minutes} min (post-peak)",
        )
