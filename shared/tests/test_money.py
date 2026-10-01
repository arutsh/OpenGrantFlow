import json
from decimal import Decimal

import pytest
from pydantic import BaseModel, ValidationError

from shared.schemas.money import Money, Rate


class _Amount(BaseModel):
    a: Money


class _OptionalAmount(BaseModel):
    a: Money | None = None


class _Rate(BaseModel):
    r: Rate


def test_json_number_parses_to_exact_decimal():
    assert _Amount.model_validate_json('{"a": 0.1}').a == Decimal("0.1")


def test_python_float_parses_to_exact_decimal():
    assert _Amount(a=0.1).a == Decimal("0.1")


def test_money_rounds_half_up_to_4_dp():
    assert _Amount(a=10.123456).a == Decimal("10.1235")
    assert _Amount(a="0.00005").a == Decimal("0.0001")


def test_rate_rounds_half_up_to_10_dp():
    assert _Rate.model_validate_json('{"r": 412.34567890123456}').r == Decimal("412.3456789012")


def test_small_rate_keeps_significant_digits():
    assert _Rate(r=0.0073125).r == Decimal("0.0073125")


def test_json_dump_emits_numbers_not_strings():
    dumped = _Amount(a=1500.5).model_dump_json()
    assert dumped == '{"a":1500.5}'
    assert isinstance(json.loads(_Rate(r="0.0073125").model_dump_json())["r"], float)


def test_python_dump_keeps_decimal():
    assert isinstance(_Amount(a=1).model_dump()["a"], Decimal)


def test_optional_money_accepts_none():
    assert _OptionalAmount().a is None
    assert _OptionalAmount(a=None).model_dump_json() == '{"a":null}'


def test_amount_too_large_for_quantize_is_rejected():
    with pytest.raises(ValidationError):
        _Amount(a="1e30")


def test_amount_exceeding_column_precision_is_rejected():
    with pytest.raises(ValidationError):
        _Amount(a="1e15")


def test_json_schema_stays_plain_number():
    props = _OptionalAmount.model_json_schema()["properties"]
    assert props["a"]["anyOf"] == [{"type": "number"}, {"type": "null"}]
    assert _Rate.model_json_schema()["properties"]["r"]["type"] == "number"
