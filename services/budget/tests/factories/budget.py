from decimal import Decimal
import factory
from uuid import uuid4
from app.models.budget import BudgetModel, BudgetLineModel, BudgetCategoryModel
from app.schemas.budget_schema import BudgetStatus


class BudgetFactory(factory.Factory):
    class Meta:
        model = BudgetModel

    id = factory.LazyFunction(uuid4)
    name = factory.Faker("word")
    owner_id = factory.LazyFunction(uuid4)
    funding_customer_id = None
    external_funder_name = factory.Faker("company")
    created_by = factory.LazyFunction(uuid4)
    updated_by = factory.LazyFunction(uuid4)
    created_at = None
    updated_at = None
    status = BudgetStatus.draft
    duration_months = 12
    local_currency = "GBP"
    actual_currency = None
    start_date = None
    donor_total_amount = None
    estimated_exchange_rate = None
    confirmed_at = None


class BudgetCategoryFactory(factory.Factory):
    class Meta:
        model = BudgetCategoryModel

    id = factory.LazyFunction(uuid4)
    budget = factory.SubFactory(BudgetFactory)
    budget_id = factory.SelfAttribute("budget.id")
    name = "Personnel"
    code = factory.LazyAttribute(lambda o: o.name.upper())


class BudgetLineFactory(factory.Factory):
    class Meta:
        model = BudgetLineModel

    id = factory.LazyFunction(uuid4)
    budget = factory.SubFactory(BudgetFactory)
    budget_id = factory.SelfAttribute("budget.id")
    category_id = factory.LazyFunction(uuid4)
    description = factory.Faker("sentence", nb_words=4)
    amount = Decimal("1000.0")
    extra_fields = None
    created_by = factory.LazyFunction(uuid4)
    updated_by = factory.LazyFunction(uuid4)
    created_at = None
    updated_at = None
    category = factory.SubFactory(
        BudgetCategoryFactory,
        budget=factory.SelfAttribute("..budget"),
        budget_id=factory.SelfAttribute("..budget_id"),
    )
