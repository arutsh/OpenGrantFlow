# /services/budget/app/schemas/budget.py
from pydantic import BaseModel, field_validator
from typing import Optional, Dict, Any, List
from uuid import UUID
from shared.schemas.audit_mixin import AuditMixinBase
from shared.schemas.money import Money


# Budget Line schema
class BudgetCategoryBase(BaseModel):
    name: str
    code: Optional[str] = None
    budget_id: UUID


class BudgetCategoryCreate(BudgetCategoryBase):
    pass


class BudgetCategoryUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_must_be_non_blank(cls, v: Optional[str]) -> str:
        # Only runs when the client explicitly sends "name" (including null),
        # since an omitted field never reaches the validator with its default.
        if v is None or not v.strip():
            raise ValueError("name must not be blank")
        return v.strip()


class BudgetCategory(BudgetCategoryBase, AuditMixinBase):
    id: UUID

    model_config = {"from_attributes": True}


class BudgetLineBase(BaseModel):

    budget_id: UUID
    description: str
    amount: Money
    extra_fields: Optional[Dict[str, Any]] = None
    category_id: Optional[UUID] = None


class BudgetLineCreate(BudgetLineBase):
    category_name: str | None = None


class BudgetLineUpdate(BaseModel):
    budget_id: UUID
    description: str | None = None
    amount: Optional[Money] = None
    extra_fields: Optional[Dict[str, Any]] = None
    category_id: Optional[UUID] = None


class BudgetLine(BudgetLineBase, AuditMixinBase):
    id: UUID
    category: Optional[BudgetCategory] = None
    model_config = {"from_attributes": True}


class BudgetLinesResponse(BaseModel):
    budget_lines: List[BudgetLine]
