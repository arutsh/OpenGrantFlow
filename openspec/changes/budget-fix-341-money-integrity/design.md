# Design

## Context

See proposal.md for motivation. Constraints on the approach:

- **Pydantic schemas are a cross-service contract.** Budget, budget-line, report-line and currency-ledger schemas live in `shared/schemas/` and are read by budget, chat and ai, and indirectly by LLM tools via chat's MCP bridge.
- **Pydantic v2 serializes `Decimal` as a JSON string by default** (`{"a":"1234.50"}`). The frontend does arithmetic on amounts in about 50 places (e.g. `receipts.reduce((sum, r) => sum + (r.amount ?? 0), 0)` in `CurrencyLedgerPanel.tsx`). A string amount there concatenates (`0 + "100.00"` → `"0100.00"`) with no error.
- **`Decimal` and `float` don't mix in Python arithmetic.** `Decimal * float` raises `TypeError`, and every current money code path mixes in float literals (`0.0`, `FLOAT_EPSILON`).
- **Unit tests run on aiosqlite.** SQLite has no native `NUMERIC`: SQLAlchemy stores the values as floats and returns `Decimal` with a warning, so unit tests exercise the types but not the precision.
- **Budget migrations are hand-numbered and sequential.** Main is at `000016`, and the unmerged `budget-feat-313-excel-export` group-5 branch adds `000017`/`000018`.

## Goals / Non-Goals

**Goals:**
- Exact storage and exact server-side arithmetic for every money and rate value in the budget service.
- No change to the JSON API contract: frontend, chat and ai keep working untouched.

**Non-Goals:**
- Exact client-side arithmetic. Frontend `reduce` sums stay float, treated as display conveniences, and move to server-computed totals opportunistically when those files are touched.
- Per-currency minor-unit rounding (JPY=0, KWD=3). A single column scale covers every ISO 4217 currency, and `pycountry` has no minor-unit data anyway.
- Money columns outside the budget service.

## Decisions

**1. Wire format: `Decimal` inside, JSON number outside.**
A shared `Money` annotated type in `shared/schemas`: `Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]` (plus a `Rate` twin). Pydantic parses JSON numbers straight from the text into `Decimal` (`0.1` → `Decimal('0.1')`, no drift), and the serializer emits plain numbers. A double holds every 2–4 dp amount below about 10¹³ exactly enough for display, and the drift being fixed is server-side (storage and sums).
*Alternatives:*
- **Decimal strings on the wire** (PayPal / Google `Money` style): exact end to end, but it changes every money field for the frontend, chat, ai and LLM tool outputs, and a missed frontend site fails silently.
- **Integer minor units** (Stripe style): exact, but it needs per-currency minor-unit data and a full rewrite, and it's the one scheme where a unit mistake is a 100× error.

A can move to strings later by changing one serializer.

**2. Column types: money `Numeric(18, 4)`, rates `Numeric(20, 10)`.**
Scale 4 covers every ISO 4217 minor unit (max 4, e.g. CLF). Rates get their own, finer scale because a rate like EUR per KES needs far more decimal places than any amount. `estimated_exchange_rate` is the only stored rate; ledger rates are derived at read time (`local_amount ÷ donor_amount`) and are computed as `Decimal`.
*Alternative:* one `Numeric(18, 4)` for everything. Rejected because it truncates small rates.

**3. Inputs are rounded to column scale, not rejected.**
`Money`/`Rate` quantize on validation (`ROUND_HALF_UP`) to scale 4/10. Chat's Excel import derives `estimated_exchange_rate = line_total / donor_total_amount` in float and sends the full double. Rejecting extra decimal places would break that path for no user benefit.

**4. Server arithmetic becomes exact.**
- **Epsilon comparisons:** `FLOAT_EPSILON` is removed. FIFO (`_consume_fifo`, `currency_conversion_crud.py`) and the Excel export compare against `Decimal(0)`.
- **SQL literals:** `func.coalesce(col, 0.0)` becomes `func.coalesce(col, 0)`. A float bind parameter makes Postgres resolve `coalesce(numeric, float8)` to `float8`, which would quietly undo the migration in `dashboard_crud.py` and `budget_crud.py`.
- **Python accumulators:** accumulators and defaults like `allocated_total = 0.0` / `line.amount or 0.0` become `Decimal(0)`.
- **Excel export:** openpyxl writes `Decimal` cells natively.

**5. Single-line writes commit once.**
Mirror #286's pattern: `create_budget_line`/`update_budget_line`/`delete_budget_line` take `commit: bool` (`update_budget_line` currently has none). The service passes `commit=False`, then calls `recalculate_budget_total(..., commit=True)`, so the line and the total land in one commit.
*Alternative:* an ORM flush event listener recalculating on any line mutation. Rejected because aggregate queries inside flush events are fragile under async sessions and hide the write from the reader of the service.

**6. `total_amount` is response-only and rejected on input.**
It moves off `BudgetBase` onto the response schemas. `BudgetCreate` and `CreateBudgetWithLinesRequest` reject it with a 422. Removing the field alone isn't enough: under Pydantic's default `extra="ignore"` it would still be silently dropped. Both input schemas therefore reject the key explicitly (a before-mode check on its presence), so the 422 in the donor-dashboard spec holds. No client sends it today (the frontend builds update payloads field by field), and the `hide=True` entries for it in chat's `mcp_bridge.py` become removable. `recalculate_budget_total` logs a warning when the budget isn't found.

**7. Currency validation lives on input schemas only.**
A `field_validator` on `BudgetCreate` and `CreateBudgetWithLinesRequest` (the update path also uses `BudgetCreate`), matching `admin_management_schema.py` in users: uppercase the code, reject anything not in ISO 4217. It is deliberately **not** on `BudgetBase`, because response schemas inherit from it and one legacy row with a bad code would turn a GET into a 500.

**8. Currency list endpoint in the budget service.**
`GET /budgets/currencies` returns `get_currency_list()` (plus names), served from the service that validates the same list, so the dropdown and the validator can't disagree. The route is registered before `GET /budgets/{budget_id}`; otherwise FastAPI tries to parse "currencies" as a UUID and returns 422.
*Alternative:* the browser's `Intl.supportedValuesOf('currency')`. Rejected because the browser's ICU list and `pycountry` can diverge, offering codes the server then rejects.

## Risks / Trade-offs

- **[Risk] A float slips into Decimal arithmetic after the migration** and raises `TypeError` at runtime, not at import. → Mitigation: grep for the conversion sites in Decision 4, plus unit tests that run every money path end to end with `Decimal` values.
- **[Risk] SQLite unit tests can't prove precision.** → Mitigation: one Postgres-backed test (e2e api suite or a dedicated integration test) that round-trips `0.1 + 0.2`-style sums and a 10-dp rate.
- **[Risk] Existing rows carry float artefacts** (e.g. `0.30000000000000004`). → Mitigation: the migration casts with `round(col::numeric, 4)` / `round(col::numeric, 10)`. Totals are recomputed from the rounded lines afterwards, so `total_amount` still equals its line sum.
- **[Trade-off] Client-side sums stay float.** Accepted under Decision 1. A ledger balance shown in the UI may be summed in JS, but the authoritative balance (`LedgerBalance`) is computed server-side.
- **[Risk] Migration number collision** with `budget-feat-313-excel-export` group 5 (`000017`/`000018`, unmerged) and `budget-feat-326-customer-profile-cache`. → Mitigation: this change lands first and takes `000017`. The group-5 branch renumbers its two migrations and their `down_revision` on rebase.

## Migration Plan

1. One Alembic migration: for each of the 9 columns, `ALTER COLUMN ... TYPE numeric(p, s) USING round(col::numeric, s)`, then recompute `budgets.total_amount` from its lines. At current data volumes the table rewrite is negligible.
2. Deploy the migration and code together in one release. Old code tolerates `numeric` columns during the brief overlap, because SQLAlchemy's `Float` type converts returned `Decimal`s to `float`.
3. **Rollback:** roll the code back first (for the same reason, it's safe on `numeric`), then optionally run the downgrade, which casts back to `double precision`. Values stay correct, and only exactness is lost.
