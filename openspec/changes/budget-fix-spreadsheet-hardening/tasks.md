# Tasks

Workflow rule: one task group = one GitHub sub-issue (of this change's parent issue) = one PR, merged before the next group starts.

## 1. Export writes untrusted values as text

- [ ] 1.0 Run `scripts/flow.py start budget-fix-spreadsheet-hardening 1` to move this group to In Progress and create its branch before starting any other work in this group.
- [ ] 1.1 Add `_write_text` / `_write_formula` helpers on `_SheetWriter` and route every user-derived write through `_write_text` (header block, category names, line and expense descriptions, extra field keys and values, audit footer) on all three sheets; verify by grepping that no `ws.cell(..., value=` call with user data remains.
- [ ] 1.2 Add a save → reload test with a fixture where every user field is a formula-like payload (`=`, `+`, `-`, `@` leads, `HYPERLINK`, `cmd|' /C calc'!A0`), asserting those cells are type `s` with their exact values; verify it fails on `main` and passes on the branch.
- [ ] 1.3 Add a test asserting the set of formula cells for the malicious fixture equals the set for a benign fixture, and that subtotal, grand total and cross-sheet actuals formulas still reference the expected cells.
- [ ] 1.4 Run `pytest services/budget` and `flake8 --max-line-length=100` clean; open one malicious export in LibreOffice/Excel locally to confirm nothing evaluates; PR merged.

## 2. Bounded, non-blocking import parsing — ticket depends on 1

- [ ] 2.0 Run `scripts/flow.py start budget-fix-spreadsheet-hardening 2` to move this group to In Progress and create its branch before starting any other work in this group.
- [ ] 2.1 Add `defusedxml` to `services/budget/requirements.txt`; verify `openpyxl.xml.DEFUSEDXML` is `True` in the budget container.
- [ ] 2.2 Implement `workbook_limits.py` (zip stage and streaming sheet-extent stage, with counted decompression); verify with unit tests built in memory: a sparse `A1` + `XFD1048576` sheet, a high-ratio member, a forged `file_size`, too many members, and a normal template that passes. Each test should finish in under 1 s with no large allocation.
- [ ] 2.3 Call the guard from `prepare_excel_import_service` before `ExcelStructureDetector`, returning 400 with the limit name and skipping storage; verify with route tests.
- [ ] 2.4 Move guard, detection and grid building into `anyio.to_thread.run_sync` with a `CapacityLimiter(2)`; verify with a test that an event-loop tick (e.g. a concurrent trivial coroutine) completes while a slow parse is stubbed in.
- [ ] 2.5 Run the new guard against the stored donor templates on dev to confirm none are rejected; run `pytest services/budget` and `flake8 --max-line-length=100` clean; PR merged.
