# Design

## Context

- The export builds three sheets through `_SheetWriter` subclasses that call `ws.cell(..., value=...)` directly. Generated formulas are f-strings starting with `=`, so "a string starting with `=`" can't tell user data from application formulas at the write site. The distinction has to be made by the caller.
- For import, `ExcelStructureDetector.__init__` calls `load_workbook(..., data_only=False)` and then `data_only=True` (non-read-only), and `read_sheet_with_openpyxl` zips `iter_rows()` over the full used range. `pd.read_excel` also exists but only as an alternative path. `prepare_excel_import_service` is `async` but does all of this synchronously.

## Goals / Non-Goals

**Goals:** no user text evaluates in Excel; bounded CPU and memory for any upload up to the size cap; no event-loop blocking.

**Non-Goals:**
- CSV export (none exists). If added later, it needs the leading-character prefix technique, because CSV has no cell types.
- Sandboxing the parse in a separate process with hard memory limits. The pre-parse caps make the work bounded; process isolation is a possible later hardening.

## Decisions

1. **Explicit writer helpers.** `_write_text(row, col, value)` sets the value and then forces `cell.data_type = "s"` for strings. `_write_formula(row, col, formula)` is the only path for generated formulas. All current `ws.cell(value=…)` calls for user data move to `_write_text`. A test walks every cell of an exported workbook built from a fixture where *every* user field is a formula-like payload. It asserts that the set of formula cells equals the set produced by the same budget with benign text. This catches any write site that was missed. *Alternative:* prefix with `'`. Rejected because it changes the displayed value and round-trips differently.
2. **Two-stage pre-parse guard** in `workbook_limits.py`, using the standard library only:
   - Zip stage: `zipfile.ZipFile.infolist()` checks member count ≤ 200, each `file_size` ≤ 50 MB, total ≤ 100 MB, and ratio ≤ 100:1 for members over 1 MB. It then reads the members while counting the bytes actually decompressed, so a forged `file_size` header can't get around the cap.
   - Sheet stage: stream each `xl/worksheets/*.xml` with `iterparse` and read only the `r` attribute of `<c>` elements. It tracks max row and column plus the cell count, and aborts as soon as rows > 10,000, columns > 500, or cells > 1,000,000.

   Starting caps: 10k rows, 500 columns, 1M cells. Real donor templates are well under 1k × 50. The caps are constants and can be tuned.
3. **After passing the guard, the existing openpyxl flow is safe as is.** Its used range is bounded by the verified max row and column. No rewrite of the detector is needed. Also add `defusedxml` so openpyxl enables its hardened parser.
4. **`anyio.to_thread.run_sync` plus a module-level `CapacityLimiter(2)`** wraps guard, detection and grid building. A thread can't be killed. That is acceptable because the guard makes the work bounded.

## Risks / Trade-offs

- [A real template exceeds a cap] → the 400 message names the limit, and the constants are easy to raise. Check against the stored templates in `budget-imports/` on dev before merging.
- [iterparse on a hostile XML] → `defusedxml.ElementTree.iterparse` is used for the scan too.
- [A missed export write site] → the cell-walk test in decision 1 is the safety net.
