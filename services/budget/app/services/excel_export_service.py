import io
from datetime import date, datetime, timezone
from uuid import UUID

from openpyxl import Workbook
from openpyxl.styles import Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.crud.budget_category_crud import list_budget_categories
from app.crud.budget_line_crud import list_budget_lines
from app.models.budget import BudgetCategoryModel, BudgetLineModel, BudgetModel
from app.services.budget_services import _add_duration_months, get_viewable_budget_service
from app.services.customer_client import CustomerServiceError, get_customer_cached
from app.services.user_cache import get_users_by_ids_cached

SHEET1_TITLE = "Original Budget"
_BOLD = Font(bold=True)
_AUDIT_FONT = Font(italic=True, size=9, color="808080")
_TOTAL_FILL = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")
_TOP_BORDER = Border(top=Side(style="thin"))
_DESCRIPTION_COL_WIDTH = 26.63
_EXTRA_COL_WIDTH = 20.0
_AMOUNT_COL_WIDTH = 17.77
_ESTIMATE_COL_WIDTH = 17.53
_HEADER_ROW_COUNT = 6
_RATE_ROW = _HEADER_ROW_COUNT
_DESCRIPTION_COL = 1


async def export_budget_workbook_service(
    db, valid_user: dict, budget_id: UUID
) -> tuple[BudgetModel, bytes]:
    """Loads one budget's categories/lines (auth: owner or funder, same as
    GET /budgets/{budget_id}) and builds its export workbook."""
    budget = await get_viewable_budget_service(budget_id, valid_user, db)
    categories = await list_budget_categories(db, budget_id=budget_id, limit=None)
    lines = await list_budget_lines(db, budget_id=budget_id, limit=None)
    organisation_name = None
    try:
        organisation_name = (await get_customer_cached(budget.owner_id)).get("name")
    except CustomerServiceError:
        pass

    donor_name = budget.external_funder_name
    if budget.funding_customer_id:
        try:
            donor_name = (await get_customer_cached(budget.funding_customer_id)).get("name")
        except CustomerServiceError:
            donor_name = budget.external_funder_name

    try:
        users = await get_users_by_ids_cached(
            [str(valid_user["user_id"])], valid_user.get("token", "")
        )
    except Exception:
        users = {}
    exported_by = users.get(str(valid_user["user_id"]), {}).get("email")
    return budget, generate_budget_export_workbook(
        budget, categories, lines,
        organisation_name=organisation_name, donor_name=donor_name,
        exported_by=exported_by, exported_at=datetime.now(timezone.utc),
    )


def generate_budget_export_workbook(
    budget: BudgetModel,
    categories: list[BudgetCategoryModel],
    lines: list[BudgetLineModel],
    organisation_name: str | None = None,
    donor_name: str | None = None,
    exported_by: str | None = None,
    exported_at: datetime | None = None,
) -> bytes:
    """Builds the export workbook for one budget. Group 1 populates only
    Sheet 1 (Original Budget); Sheets 2/3 land in later task groups."""
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET1_TITLE
    _write_sheet1(
        ws, budget, categories, lines, organisation_name, donor_name, exported_by, exported_at
    )

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _period_label(start_date: date | None, duration_months: int | None) -> str | None:
    if not start_date:
        return None
    if not duration_months:  # None (unset) and 0 (BudgetModel's column default) both mean "unknown"
        return start_date.strftime("%m/%Y")
    end_date = _add_duration_months(start_date, duration_months - 1)
    return f"{start_date.strftime('%m/%Y')}-{end_date.strftime('%m/%Y')}"


def _currency_format(currency: str | None) -> str:
    return f'#,##0.00" {currency}"' if currency else "#,##0.00"


def _bold_row(ws, row: int) -> None:
    for cell in ws[row]:
        cell.font = _BOLD


def _apply_box_border(ws, start_row: int, end_row: int, end_col: int) -> None:
    thin = Side(style="thin")
    for row in range(start_row, end_row + 1):
        for column in range(1, end_col + 1):
            ws.cell(row=row, column=column).border = Border(
                top=thin if row == start_row else None,
                bottom=thin if row == end_row else None,
                left=thin if column == 1 else None,
                right=thin if column == end_col else None,
            )


def _extra_field_keys(lines: list[BudgetLineModel]) -> list[str]:
    """Distinct extra_fields keys across the budget, in first-seen order."""
    keys: dict = {}
    for line in lines:
        for key in line.extra_fields or {}:
            keys[key] = None
    return list(keys)


def _amount_columns(extra_keys: list[str]) -> dict:
    """Amount/Estimate shift right by one column per distinct extra field key."""
    amount_col = _DESCRIPTION_COL + 1 + len(extra_keys)
    estimate_col = amount_col + 1
    return {
        "amount_col": amount_col,
        "estimate_col": estimate_col,
        "amount_letter": get_column_letter(amount_col),
        "estimate_letter": get_column_letter(estimate_col),
    }


def _plan_rows(ordered_category_ids: list, lines_by_category_id: dict) -> dict:
    """Computes every row number up front — Budget Summary formulas reference
    Detailed Budget's subtotal rows before those rows are written."""
    summary_header_row = _RATE_ROW + 3
    summary_rows = {}
    row = summary_header_row
    for category_id in ordered_category_ids:
        row += 1
        summary_rows[category_id] = row
    summary_total_row = row + 1 if ordered_category_ids else summary_header_row + 1

    detail_title_row = summary_total_row + 2
    detail_header_rows: dict = {}
    detail_line_rows: dict = {}
    detail_subtotal_rows: dict = {}
    row = detail_title_row
    for category_id in ordered_category_ids:
        row += 1
        detail_header_rows[category_id] = row
        line_rows = []
        for _ in lines_by_category_id.get(category_id, []):
            row += 1
            line_rows.append(row)
        detail_line_rows[category_id] = line_rows
        row += 1
        detail_subtotal_rows[category_id] = row
        row += 1  # blank separator after the category block

    footer_total_row = row + 2 if ordered_category_ids else detail_title_row + 2
    signature_line_row = footer_total_row + 3
    contact_line_row = signature_line_row + 4
    audit_row = contact_line_row + 3

    return {
        "summary_header_row": summary_header_row,
        "summary_rows": summary_rows,
        "summary_total_row": summary_total_row,
        "detail_title_row": detail_title_row,
        "detail_header_rows": detail_header_rows,
        "detail_line_rows": detail_line_rows,
        "detail_subtotal_rows": detail_subtotal_rows,
        "footer_total_row": footer_total_row,
        "signature_line_row": signature_line_row,
        "contact_line_row": contact_line_row,
        "audit_row": audit_row,
    }


def _write_sheet1(
    ws,
    budget: BudgetModel,
    categories: list[BudgetCategoryModel],
    lines: list[BudgetLineModel],
    organisation_name: str | None,
    donor_name: str | None,
    exported_by: str | None,
    exported_at: datetime | None,
) -> None:
    has_rate = bool(budget.estimated_exchange_rate)
    rate_cell = _write_header(ws, budget, organisation_name, donor_name)

    local_fmt = _currency_format(budget.local_currency)
    estimate_fmt = _currency_format(budget.actual_currency)
    amount_header = f"Amount ({budget.local_currency})" if budget.local_currency else "Amount"
    estimate_header = (
        f"Estimate ({budget.actual_currency})" if budget.actual_currency else "Donor Estimate"
    )

    categories_by_id = {category.id: category for category in categories}
    lines_by_category_id: dict = {}
    for line in lines:
        category = categories_by_id.get(line.category_id)
        lines_by_category_id.setdefault(category.id if category else None, []).append(line)

    # categories/lines already arrive ordered by created_at, id from the CRUD queries.
    ordered_category_ids = list(categories_by_id)
    if None in lines_by_category_id:
        ordered_category_ids.append(None)

    category_names = {
        cid: (categories_by_id[cid].name if cid else "Uncategorized")
        for cid in ordered_category_ids
    }
    category_lines = {
        cid: lines_by_category_id.get(cid, []) for cid in ordered_category_ids
    }
    extra_keys = _extra_field_keys(lines)
    cols = _amount_columns(extra_keys)
    _set_column_widths(ws, extra_keys, cols)

    plan = _plan_rows(ordered_category_ids, lines_by_category_id)

    _write_budget_summary(
        ws, plan, ordered_category_ids, category_names, amount_header, estimate_header,
        extra_keys, cols, local_fmt, estimate_fmt, has_rate,
    )
    _write_detailed_budget(
        ws, plan, ordered_category_ids, category_names, category_lines, extra_keys, cols,
        local_fmt, estimate_fmt, has_rate, rate_cell,
    )
    _write_footer(
        ws, plan, ordered_category_ids, cols, local_fmt, estimate_fmt, has_rate,
        exported_by, exported_at,
    )


def _set_column_widths(ws, extra_keys: list[str], cols: dict) -> None:
    ws.column_dimensions[get_column_letter(_DESCRIPTION_COL)].width = _DESCRIPTION_COL_WIDTH
    for i in range(len(extra_keys)):
        ws.column_dimensions[get_column_letter(_DESCRIPTION_COL + 1 + i)].width = _EXTRA_COL_WIDTH
    ws.column_dimensions[get_column_letter(cols["amount_col"])].width = _AMOUNT_COL_WIDTH
    ws.column_dimensions[get_column_letter(cols["estimate_col"])].width = _ESTIMATE_COL_WIDTH


def _write_header(
    ws, budget: BudgetModel, organisation_name: str | None, donor_name: str | None
) -> str:
    """Writes the header block and returns the rate cell ref for formulas."""
    fields = (
        ("Organisation Name", organisation_name),
        ("Donor Name", donor_name),
        ("Project Name", budget.name),
        ("Project Period", _period_label(budget.start_date, budget.duration_months)),
        ("Estimated Currency", budget.actual_currency),
        ("Estimated Exchange Rate", budget.estimated_exchange_rate),
    )
    for row, (label, value) in enumerate(fields, start=1):
        ws.cell(row=row, column=1, value=label)
        ws.cell(row=row, column=2, value=value)
        _bold_row(ws, row)

    return f"$B${_RATE_ROW}"


def _write_budget_summary(
    ws, plan, ordered_category_ids, category_names, amount_header, estimate_header,
    extra_keys, cols, local_fmt, estimate_fmt, has_rate,
) -> None:
    amount_col, estimate_col = cols["amount_col"], cols["estimate_col"]
    amount_letter, estimate_letter = cols["amount_letter"], cols["estimate_letter"]

    header_row = plan["summary_header_row"]
    ws.cell(row=header_row, column=1, value="BUDGET SUMMARY")
    for i, key in enumerate(extra_keys):
        ws.cell(row=header_row, column=_DESCRIPTION_COL + 1 + i, value=key)
    ws.cell(row=header_row, column=amount_col, value=amount_header)
    ws.cell(row=header_row, column=estimate_col, value=estimate_header)
    _bold_row(ws, header_row)

    for category_id in ordered_category_ids:
        row = plan["summary_rows"][category_id]
        detail_subtotal_row = plan["detail_subtotal_rows"][category_id]
        ws.cell(row=row, column=1, value=category_names[category_id])
        _set_cell(ws, row, amount_col, f"={amount_letter}{detail_subtotal_row}", local_fmt)
        if has_rate:
            _set_cell(
                ws, row, estimate_col, f"={estimate_letter}{detail_subtotal_row}", estimate_fmt
            )
    if ordered_category_ids:
        first_summary_row = plan["summary_rows"][ordered_category_ids[0]]
        last_summary_row = plan["summary_rows"][ordered_category_ids[-1]]
        _apply_box_border(ws, first_summary_row, last_summary_row, estimate_col)

    total_row = plan["summary_total_row"]
    ws.cell(row=total_row, column=1, value="TOTAL")
    if ordered_category_ids:
        first_row = plan["summary_rows"][ordered_category_ids[0]]
        last_row = plan["summary_rows"][ordered_category_ids[-1]]
        amount_range = f"{amount_letter}{first_row}:{amount_letter}{last_row}"
        _set_cell(ws, total_row, amount_col, f"=SUM({amount_range})", local_fmt)
        if has_rate:
            estimate_range = f"{estimate_letter}{first_row}:{estimate_letter}{last_row}"
            _set_cell(ws, total_row, estimate_col, f"=SUM({estimate_range})", estimate_fmt)
    else:
        _set_cell(ws, total_row, amount_col, 0.0, local_fmt)
    _bold_row(ws, total_row)


def _write_detailed_budget(
    ws, plan, ordered_category_ids, category_names, category_lines, extra_keys, cols,
    local_fmt, estimate_fmt, has_rate, rate_cell,
) -> None:
    amount_col, estimate_col = cols["amount_col"], cols["estimate_col"]
    amount_letter, estimate_letter = cols["amount_letter"], cols["estimate_letter"]

    ws.cell(row=plan["detail_title_row"], column=1, value="DETAILED BUDGET")
    _bold_row(ws, plan["detail_title_row"])

    for category_id in ordered_category_ids:
        header_row = plan["detail_header_rows"][category_id]
        ws.cell(row=header_row, column=1, value=category_names[category_id])
        _bold_row(ws, header_row)

        line_rows = plan["detail_line_rows"][category_id]
        for line, row in zip(category_lines[category_id], line_rows):
            ws.cell(row=row, column=1, value=line.description)
            for i, key in enumerate(extra_keys):
                value = (line.extra_fields or {}).get(key)
                ws.cell(row=row, column=_DESCRIPTION_COL + 1 + i, value=value)
            _set_cell(ws, row, amount_col, line.amount or 0.0, local_fmt)
            if has_rate:
                _set_cell(ws, row, estimate_col, f"={amount_letter}{row}/{rate_cell}", estimate_fmt)
        if line_rows:
            _apply_box_border(ws, line_rows[0], line_rows[-1], estimate_col)

        subtotal_row = plan["detail_subtotal_rows"][category_id]
        ws.cell(row=subtotal_row, column=1, value="Subtotal")
        if line_rows:
            amount_range = f"{amount_letter}{line_rows[0]}:{amount_letter}{line_rows[-1]}"
            _set_cell(ws, subtotal_row, amount_col, f"=SUM({amount_range})", local_fmt)
            if has_rate:
                estimate_range = (
                    f"{estimate_letter}{line_rows[0]}:{estimate_letter}{line_rows[-1]}"
                )
                _set_cell(ws, subtotal_row, estimate_col, f"=SUM({estimate_range})", estimate_fmt)
        else:
            _set_cell(ws, subtotal_row, amount_col, 0.0, local_fmt)
            if has_rate:
                formula = f"={amount_letter}{subtotal_row}/{rate_cell}"
                _set_cell(ws, subtotal_row, estimate_col, formula, estimate_fmt)
        _bold_row(ws, subtotal_row)


def _audit_line(exported_by: str | None, exported_at: datetime | None) -> str:
    parts = ["Generated by OpenGrantFlow"]
    if exported_by:
        parts.append(exported_by)
    if exported_at:
        parts.append(exported_at.strftime("%Y-%m-%d %H:%M UTC"))
    return " · ".join(parts)


def _write_footer(
    ws, plan, ordered_category_ids, cols, local_fmt, estimate_fmt, has_rate,
    exported_by, exported_at,
) -> None:
    amount_col, estimate_col = cols["amount_col"], cols["estimate_col"]
    amount_letter, estimate_letter = cols["amount_letter"], cols["estimate_letter"]

    total_row = plan["footer_total_row"]
    ws.cell(row=total_row, column=1, value="Total expenditures")
    if ordered_category_ids:
        subtotal_rows = [plan["detail_subtotal_rows"][cid] for cid in ordered_category_ids]
        c_formula = "=" + "+".join(f"{amount_letter}{r}" for r in subtotal_rows)
        _set_cell(ws, total_row, amount_col, c_formula, local_fmt)
        if has_rate:
            d_formula = "=" + "+".join(f"{estimate_letter}{r}" for r in subtotal_rows)
            _set_cell(ws, total_row, estimate_col, d_formula, estimate_fmt)
    else:
        _set_cell(ws, total_row, amount_col, 0.0, local_fmt)
    for cell in ws[total_row]:
        cell.font = _BOLD
        cell.fill = _TOTAL_FILL

    signature_row = plan["signature_line_row"]
    ws.cell(row=signature_row, column=1).border = _TOP_BORDER
    ws.cell(row=signature_row + 1, column=1, value="Authorised Signatory")

    contact_row = plan["contact_line_row"]
    ws.cell(row=contact_row, column=1).border = _TOP_BORDER
    ws.cell(row=contact_row + 1, column=1, value="Project contact person")

    audit_cell = ws.cell(
        row=plan["audit_row"], column=1, value=_audit_line(exported_by, exported_at)
    )
    audit_cell.font = _AUDIT_FONT


def _set_cell(ws, row: int, column: int, value, number_format: str):
    cell = ws.cell(row=row, column=column, value=value)
    cell.number_format = number_format
    return cell
