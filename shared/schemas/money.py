from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Annotated

from pydantic import AfterValidator, PlainSerializer, WithJsonSchema

MONEY_QUANTUM = Decimal("0.0001")
RATE_QUANTUM = Decimal("0.0000000001")
# Matches the Numeric(18, 4) column type used for money columns.
MONEY_MAX = Decimal("99999999999999.9999")
MONEY_MIN = -MONEY_MAX
# Matches the Numeric(20, 10) column type used for exchange-rate columns.
RATE_MAX = Decimal("9999999999.9999999999")
RATE_MIN = -RATE_MAX


def _quantizer(
    quantum: Decimal,
    min_value: Decimal | None = None,
    max_value: Decimal | None = None,
):
    def quantize(value: Decimal) -> Decimal:
        try:
            result = value.quantize(quantum, rounding=ROUND_HALF_UP)
        except InvalidOperation as exc:
            raise ValueError("Value is too large or imprecise") from exc
        if max_value is not None and result > max_value:
            raise ValueError(f"Value must not exceed {max_value}")
        if min_value is not None and result < min_value:
            raise ValueError(f"Value must not be less than {min_value}")
        return result

    return quantize


# Decimal in Python, JSON number on the wire and in the schema (OpenAPI, LLM tools).
Money = Annotated[
    Decimal,
    AfterValidator(_quantizer(MONEY_QUANTUM, MONEY_MIN, MONEY_MAX)),
    PlainSerializer(float, return_type=float, when_used="json"),
    WithJsonSchema({"type": "number"}),
]

# Same rounding as Money, but unbounded — for read-time calculated values
# (e.g. estimated_local_cap, dashboard aggregates) not stored in a column.
CalculatedMoney = Annotated[
    Decimal,
    AfterValidator(_quantizer(MONEY_QUANTUM)),
    PlainSerializer(float, return_type=float, when_used="json"),
    WithJsonSchema({"type": "number"}),
]

Rate = Annotated[
    Decimal,
    AfterValidator(_quantizer(RATE_QUANTUM, RATE_MIN, RATE_MAX)),
    PlainSerializer(float, return_type=float, when_used="json"),
    WithJsonSchema({"type": "number"}),
]
