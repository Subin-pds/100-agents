"""Tests for the recovery agent. All tests use DRY_RUN=true — zero real API calls."""
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ["DRY_RUN"] = "true"
os.environ.setdefault("MAX_RETRY_ATTEMPTS", "3")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("RAZORPAY_KEY_ID", "test-id")
os.environ.setdefault("RAZORPAY_KEY_SECRET", "test-secret")

from agent.classifier import ClassifiedPayment, FailureType
from agent.recovery import RecoveryAgent, RecoveryState
from tests.mock_payments import get_mock_payment


def make_classified(
    payment_id: str,
    failure_type: FailureType,
    amount: int = 100000,
) -> ClassifiedPayment:
    raw = get_mock_payment(payment_id) or {"id": payment_id, "contact": "cust_test"}
    return ClassifiedPayment(
        payment_id=payment_id,
        amount=amount,
        failure_type=failure_type,
        recovery_strategy="test",
        recovery_probability=0.8,
        priority_score=(amount / 100) * 0.8,
        raw_payment=raw,
    )


def run(coro):
    return asyncio.run(coro)


class TestRecoveryState:
    def test_allows_attempts_under_cap(self) -> None:
        state = RecoveryState(max_attempts=3)
        assert state.can_attempt("pay_001")

    def test_blocks_at_cap(self) -> None:
        state = RecoveryState(max_attempts=2)
        state.record_attempt("pay_001")
        state.record_attempt("pay_001")
        assert not state.can_attempt("pay_001")

    def test_different_payments_are_independent(self) -> None:
        state = RecoveryState(max_attempts=1)
        state.record_attempt("pay_001")
        assert not state.can_attempt("pay_001")
        assert state.can_attempt("pay_002")

    def test_link_cap_enforced(self) -> None:
        state = RecoveryState(max_attempts=3, max_links_per_day=2)
        state.record_link_sent("cust_001")
        state.record_link_sent("cust_001")
        assert not state.can_send_link("cust_001")

    def test_different_customers_are_independent(self) -> None:
        state = RecoveryState(max_attempts=3, max_links_per_day=1)
        state.record_link_sent("cust_001")
        assert not state.can_send_link("cust_001")
        assert state.can_send_link("cust_002")


class TestRecoveryAgentDryRun:
    """All tests in DRY_RUN=true — mock client should never be called."""

    def setup_method(self) -> None:
        self.mock_client = MagicMock()
        self.mock_client.call_tool = AsyncMock()
        self.agent = RecoveryAgent(self.mock_client)

    def _recover(self, classified: ClassifiedPayment):
        return run(self.agent.recover(classified))

    def test_bank_technical_dry_run_succeeds(self) -> None:
        result = self._recover(make_classified("pay_bank_001", FailureType.BANK_TECHNICAL))
        assert result.success
        assert result.dry_run
        assert "DRY RUN" in result.detail
        self.mock_client.call_tool.assert_not_called()

    def test_insufficient_funds_dry_run_succeeds(self) -> None:
        result = self._recover(make_classified("pay_insuf_001", FailureType.INSUFFICIENT_FUNDS))
        assert result.success
        assert result.dry_run
        self.mock_client.call_tool.assert_not_called()

    def test_card_expired_dry_run_succeeds(self) -> None:
        result = self._recover(make_classified("pay_card_exp_001", FailureType.CARD_EXPIRED))
        assert result.success
        assert result.dry_run
        self.mock_client.call_tool.assert_not_called()

    def test_upi_timeout_dry_run_succeeds(self) -> None:
        result = self._recover(make_classified("pay_upi_001", FailureType.UPI_TIMEOUT))
        assert result.success
        assert result.dry_run
        self.mock_client.call_tool.assert_not_called()

    def test_max_attempts_blocks_recovery(self) -> None:
        classified = make_classified("pay_bank_001", FailureType.BANK_TECHNICAL)
        for _ in range(3):
            self.agent._state.record_attempt("pay_bank_001")
        result = self._recover(classified)
        assert not result.success
        assert result.action_taken == "skipped"

    def test_link_cap_blocks_card_expired(self) -> None:
        classified = make_classified("pay_card_exp_001", FailureType.CARD_EXPIRED)
        customer_id = classified.raw_payment.get("contact", classified.payment_id)
        self.agent._state.record_link_sent(customer_id)
        self.agent._state.record_link_sent(customer_id)
        result = self._recover(classified)
        assert not result.success
        assert "cap" in result.action_taken

    def test_unknown_failure_type_returns_no_action(self) -> None:
        classified = make_classified("pay_unk_001", FailureType.UNKNOWN)
        result = self._recover(classified)
        assert not result.success
        assert result.action_taken == "no_action"
