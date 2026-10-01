from decimal import Decimal
import factory
from uuid import uuid4
from datetime import date

from app.models.report import ReportModel, ReportLineModel
from app.schemas.report_schema import ReportStatus


class ReportFactory(factory.Factory):
    class Meta:
        model = ReportModel

    id = factory.LazyFunction(uuid4)
    budget_id = factory.LazyFunction(uuid4)
    name = factory.Faker("sentence", nb_words=3)
    status = ReportStatus.draft
    period_start = date(2026, 1, 1)
    period_end = date(2026, 12, 31)
    submitted_at = None
    reviewed_at = None
    reviewed_by = None
    review_notes = None
    created_by = factory.LazyFunction(uuid4)
    updated_by = factory.LazyFunction(uuid4)
    created_at = None
    updated_at = None


class ReportLineFactory(factory.Factory):
    class Meta:
        model = ReportLineModel

    id = factory.LazyFunction(uuid4)
    report_id = factory.LazyFunction(uuid4)
    budget_line_id = factory.LazyFunction(uuid4)
    description = factory.Faker("sentence", nb_words=4)
    amount = Decimal("250.0")
    expense_date = date(2026, 6, 15)
    extra_fields = None
    created_by = factory.LazyFunction(uuid4)
    updated_by = factory.LazyFunction(uuid4)
    created_at = None
    updated_at = None
