"""Tests for the payment failure classifier.

Offline tests use mock data only — no Anthropic API key needed.
Integration tests (marked skip) require a real ANTHROPIC_API_KEY.
"""
import os

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("RAZORPAY_KEY_ID", "test-id")
os.environ.setdefault("RAZORPAY_KEY_SECRET", "test-secret")
os.environ.setdefault("DRY_RUN", "true")

from agent.classifier import ClassifiedPayment, FailureType
from tests.mock_payments import MOCK_PAYMENTS, get_mock_payment


class TestFailureTypeEnum:
    def test_all_five_types_defined(self) -> None:
        expected = {
            "BANK_TECHNICAL", "INSUFFICIENT_FUNDS",
            "CARD_EXPIRED", "UPI_TIMEOUT", "EVENING_PEAK", "UNKNOWN",
        }
        assert {ft.value for ft in FailureType} == expected


class TestMockPaymentData:
    """Validates mock fixtures — no API calls, instant feedback."""

    def test_all_payments_have_required_fields(self) -> None:
        required = {"id", "amount", "status", "method", "error_code", "created_at"}
        for p in MOCK_PAYMENTS:
            missing = required - set(p.keys())
            assert not missing, f"{p['id']} missing fields: {missing}"

    def test_all_mock_payments_are_failed(self) -> None:
        for p in MOCK_PAYMENTS:
            assert p["status"] == "failed", f"{p['id']} is not failed"

    def test_mock_covers_upi_method(self) -> None:
        assert any(p["method"] == "upi" for p in MOCK_PAYMENTS)

    def test_mock_covers_insufficient_funds_signal(self) -> None:
        descriptions = " ".join(p.get("error_description", "") for p in MOCK_PAYMENTS)
        assert "INSUFFICIENT" in descriptions

    def test_mock_covers_expired_card_signal(self) -> None:
        descriptions = " ".join(p.get("error_description", "") for p in MOCK_PAYMENTS)
        assert "EXPIRED" in descriptions

    def test_lookup_by_id(self) -> None:
        p = get_mock_payment("pay_bank_001")
        assert p is not None
        assert p["amount"] == 1500000  # ₹15,000

    def test_lookup_missing_returns_none(self) -> None:
        assert get_mock_payment("pay_nonexistent") is None

    def test_five_mock_payments_exist(self) -> None:
        assert len(MOCK_PAYMENTS) == 5


@pytest.mark.skipif(
    os.environ.get("ANTHROPIC_API_KEY", "").startswith("test"),
    reason="Requires real ANTHROPIC_API_KEY",
)
class TestClassifierWithClaude:
    """Integration tests — set ANTHROPIC_API_KEY to a real key to run."""

    def test_classifies_bank_technical(self) -> None:
        from agent.classifier import PaymentClassifier
        result = PaymentClassifier().classify(get_mock_payment("pay_bank_001"))
        assert result.failure_type == FailureType.BANK_TECHNICAL
        assert result.recovery_probability > 0.5

    def test_classifies_insufficient_funds(self) -> None:
        from agent.classifier import PaymentClassifier
        result = PaymentClassifier().classify(get_mock_payment("pay_insuf_001"))
        assert result.failure_type == FailureType.INSUFFICIENT_FUNDS

    def test_classifies_card_expired(self) -> None:
        from agent.classifier import PaymentClassifier
        result = PaymentClassifier().classify(get_mock_payment("pay_card_exp_001"))
        assert result.failure_type == FailureType.CARD_EXPIRED

    def test_classifies_upi_timeout(self) -> None:
        from agent.classifier import PaymentClassifier
        result = PaymentClassifier().classify(get_mock_payment("pay_upi_001"))
        assert result.failure_type == FailureType.UPI_TIMEOUT

    def test_batch_sorted_by_priority_descending(self) -> None:
        from agent.classifier import PaymentClassifier
        results = PaymentClassifier().classify_batch(MOCK_PAYMENTS)
        scores = [r.priority_score for r in results]
        assert scores == sorted(scores, reverse=True)
