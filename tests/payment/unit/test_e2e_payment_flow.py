"""
Payment Validation Edge Cases Tests

Tests payment validation edge cases and boundary conditions:
- Tolerance boundary validation (0.1%)
- Satoshi-level precision handling
- Penalty calculation accuracy

Run with:
    pytest tests/payment/unit/test_e2e_payment_flow.py -v
"""

import pytest
from datetime import datetime, timedelta


class TestPaymentValidationEdgeCases:
    """Test payment validation edge cases"""

    def test_tolerance_boundary_cases(self):
        """Test 0.1% tolerance boundary"""
        from services.payment_validator import PaymentValidator
        from enums.cryptocurrency import Cryptocurrency
        from enums.payment_validation import PaymentValidationResult

        deadline = datetime.now() + timedelta(minutes=15)

        # Exactly 0.1% overpayment → MINOR_OVERPAYMENT
        result = PaymentValidator.validate_payment(
            paid=1.001,
            required=1.0,
            currency_paid=Cryptocurrency.BTC,
            currency_required=Cryptocurrency.BTC,
            deadline=deadline
        )
        assert result == PaymentValidationResult.MINOR_OVERPAYMENT

        # Just above 0.1% → OVERPAYMENT
        result = PaymentValidator.validate_payment(
            paid=1.00101,
            required=1.0,
            currency_paid=Cryptocurrency.BTC,
            currency_required=Cryptocurrency.BTC,
            deadline=deadline
        )
        assert result == PaymentValidationResult.OVERPAYMENT

    def test_very_small_amounts(self):
        """Test payment validation with satoshi-level amounts"""
        from services.payment_validator import PaymentValidator
        from enums.cryptocurrency import Cryptocurrency
        from enums.payment_validation import PaymentValidationResult

        deadline = datetime.now() + timedelta(minutes=15)

        # 1 satoshi underpayment
        result = PaymentValidator.validate_payment(
            paid=0.00000099,
            required=0.00000100,
            currency_paid=Cryptocurrency.BTC,
            currency_required=Cryptocurrency.BTC,
            deadline=deadline
        )
        assert result == PaymentValidationResult.UNDERPAYMENT

    def test_penalty_calculation_precision(self):
        """Test penalty calculation with various amounts"""
        from services.payment_validator import PaymentValidator

        # 5% of 100 EUR = 5 EUR
        penalty, net = PaymentValidator.calculate_penalty(100.0, 5.0)
        assert penalty == 5.0
        assert net == 95.0

        # 5% of 45 EUR = 2.25 EUR
        penalty, net = PaymentValidator.calculate_penalty(45.0, 5.0)
        assert penalty == 2.25
        assert net == 42.75

        # 5% of 0.01 EUR (edge case)
        # Result: 0.0005 EUR rounds DOWN to 0.00 EUR (favors customer)
        penalty, net = PaymentValidator.calculate_penalty(0.01, 5.0)
        assert penalty == 0.0  # Rounded down to 2 decimals
        assert net == 0.01  # Full amount kept (no penalty applied due to rounding)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
