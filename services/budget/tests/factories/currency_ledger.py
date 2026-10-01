from decimal import Decimal
import factory
from uuid import uuid4
from datetime import date

from app.models.currency_ledger import FundingReceiptModel, CurrencyConversionModel


class FundingReceiptFactory(factory.Factory):
    class Meta:
        model = FundingReceiptModel

    id = factory.LazyFunction(uuid4)
    budget_id = factory.LazyFunction(uuid4)
    amount = Decimal("1000.0")
    received_at = date(2026, 1, 1)
    created_by = factory.LazyFunction(uuid4)
    updated_by = factory.LazyFunction(uuid4)
    created_at = None
    updated_at = None


class CurrencyConversionFactory(factory.Factory):
    class Meta:
        model = CurrencyConversionModel

    id = factory.LazyFunction(uuid4)
    budget_id = factory.LazyFunction(uuid4)
    donor_amount = Decimal("500.0")
    local_amount = Decimal("550.0")
    converted_at = date(2026, 1, 2)
    created_by = factory.LazyFunction(uuid4)
    updated_by = factory.LazyFunction(uuid4)
    created_at = None
    updated_at = None
