"""Pre-parse safety caps for uploaded workbooks (see design.md Decision 2)."""

import io
import posixpath
import re
import struct
import zipfile
import zlib

from defusedxml.ElementTree import iterparse, parse

MAX_ZIP_MEMBERS = 200
MAX_MEMBER_SIZE = 50 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_SIZE = 100 * 1024 * 1024
MAX_COMPRESSION_RATIO = 100
RATIO_CHECK_THRESHOLD = 1024 * 1024
DECOMPRESS_CHUNK_SIZE = 1024 * 1024

MAX_ROWS = 10_000
MAX_COLUMNS = 500
MAX_CELLS = 1_000_000

_SHEET_PATH_PATTERN = re.compile(r"^xl/worksheets/sheet\d+\.xml$")
_CELL_REF_PATTERN = re.compile(r"^([A-Z]+)(\d+)$")
_WORKSHEET_REL_TYPES = {
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet",
    "http://purl.oclc.org/ooxml/officeDocument/relationships/worksheet",
}

_ALLOWED_MEMBER_EXACT = ("[Content_Types].xml",)
_ALLOWED_MEMBER_PREFIXES = ("_rels/", "xl/", "docProps/", "customXml/", "docMetadata/")


class WorkbookRejectedError(Exception):
    """Base for any pre-parse rejection; `reason` is a stable machine code."""

    def __init__(self, reason: str, detail: str):
        self.reason = reason
        super().__init__(f"{reason}: {detail}")


class WorkbookTooLargeError(WorkbookRejectedError):
    """Raised when an uploaded workbook exceeds a pre-parse safety cap."""


class InvalidWorkbookError(WorkbookRejectedError):
    """Raised when an upload is malformed or isn't a plain xlsx package."""


def _column_index(letters: str) -> int:
    index = 0
    for ch in letters:
        index = index * 26 + (ord(ch) - ord("A") + 1)
    return index


def _check_declared_zip_bounds(zf: zipfile.ZipFile) -> None:
    infos = zf.infolist()
    if len(infos) > MAX_ZIP_MEMBERS:
        raise WorkbookTooLargeError("max_zip_members", f"{len(infos)} members")

    declared_total = 0
    for info in infos:
        if info.file_size > MAX_MEMBER_SIZE:
            raise WorkbookTooLargeError("max_member_size", f"{info.filename} declares oversized")
        if info.file_size > RATIO_CHECK_THRESHOLD:
            ratio = info.file_size / max(info.compress_size, 1)
            if ratio > MAX_COMPRESSION_RATIO:
                raise WorkbookTooLargeError(
                    "max_compression_ratio", f"{info.filename} ratio {ratio:.0f}:1"
                )
        declared_total += info.file_size
    if declared_total > MAX_TOTAL_UNCOMPRESSED_SIZE:
        raise WorkbookTooLargeError("max_total_uncompressed_size", f"{declared_total} bytes")


def _check_member_allowlist(zf: zipfile.ZipFile) -> None:
    """Rejects a "polyglot" archive smuggling a member outside the expected
    `.xlsx` package parts (see design.md Decision 5)."""
    for info in zf.infolist():
        name = info.filename
        if name.startswith("/") or ".." in name.split("/"):
            raise InvalidWorkbookError("unexpected_member", name)
        if name not in _ALLOWED_MEMBER_EXACT and not name.startswith(_ALLOWED_MEMBER_PREFIXES):
            raise InvalidWorkbookError("unexpected_member", name)


def _iter_raw_member_bytes(zf: zipfile.ZipFile, info: zipfile.ZipInfo):
    """Yields a member's raw compressed bytes straight from the archive —
    bypasses `ZipExtFile`'s read-truncation to the (possibly forged) declared size."""
    fp = zf.fp
    if fp is None:
        raise InvalidWorkbookError("invalid_workbook", "archive is closed")
    fp.seek(info.header_offset)
    fname_len, extra_len = struct.unpack("<HH", fp.read(30)[26:30])
    fp.seek(info.header_offset + 30 + fname_len + extra_len)
    remaining = info.compress_size
    while remaining > 0:
        chunk = fp.read(min(remaining, DECOMPRESS_CHUNK_SIZE))
        if not chunk:
            break
        remaining -= len(chunk)
        yield chunk


def _check_actual_decompressed_size(zf: zipfile.ZipFile) -> None:
    """Decompresses every member's raw bytes itself, counting real output as it's
    produced — so a forged `file_size` header can't hide an oversized payload."""
    total = 0
    for info in zf.infolist():
        if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raise InvalidWorkbookError("unsupported_compression", info.filename)
        is_deflated = info.compress_type == zipfile.ZIP_DEFLATED
        decompressor = zlib.decompressobj(-zlib.MAX_WBITS) if is_deflated else None
        member_total = 0
        for raw_chunk in _iter_raw_member_bytes(zf, info):
            pending = raw_chunk
            while pending:
                if decompressor is None:
                    out, pending = pending, b""
                else:
                    out = decompressor.decompress(pending, DECOMPRESS_CHUNK_SIZE)
                    pending = decompressor.unconsumed_tail
                member_total += len(out)
                total += len(out)
                if member_total > MAX_MEMBER_SIZE:
                    raise WorkbookTooLargeError("max_member_size", f"{info.filename} decompressed")
                if total > MAX_TOTAL_UNCOMPRESSED_SIZE:
                    raise WorkbookTooLargeError("max_total_uncompressed_size", "decompressed total")


def _worksheet_paths(zf: zipfile.ZipFile) -> list[str]:
    """Find worksheet targets even when their package paths are nonstandard.

    Inspect package relationships rather than assuming the workbook itself
    lives at xl/workbook.xml. Keep conventional sheets in the scan as well.
    """
    names = set(zf.namelist())
    sheets = {name for name in names if _SHEET_PATH_PATTERN.match(name)}
    for name in sorted(names):
        if not name.endswith(".rels") or posixpath.basename(posixpath.dirname(name)) != "_rels":
            continue
        source_dir = posixpath.dirname(posixpath.dirname(name))
        with zf.open(name) as rels_file:
            relationships = parse(rels_file).getroot()
        for relationship in relationships:
            if relationship.get("Type") not in _WORKSHEET_REL_TYPES:
                continue
            target = relationship.get("Target")
            if relationship.get("TargetMode") == "External" or not target:
                raise InvalidWorkbookError("invalid_workbook", "invalid worksheet target")
            path = posixpath.normpath(
                target.lstrip("/") if target.startswith("/") else posixpath.join(source_dir, target)
            )
            if path.startswith("../") or path not in names:
                raise InvalidWorkbookError("invalid_workbook", "missing worksheet target")
            sheets.add(path)
    return sorted(sheets)


def _check_coordinate(name: str, row: int, column: int) -> None:
    if row < 1 or column < 1:
        raise InvalidWorkbookError("invalid_workbook", f"{name} invalid coordinate")
    if row > MAX_ROWS:
        raise WorkbookTooLargeError("max_rows", f"{name} row {row}")
    if column > MAX_COLUMNS:
        raise WorkbookTooLargeError("max_columns", f"{name} column {column}")


def _cell_coordinate(ref: str) -> tuple[int, int]:
    match = _CELL_REF_PATTERN.fullmatch(ref.upper())
    if not match:
        raise InvalidWorkbookError("invalid_workbook", "invalid cell reference")
    return int(match.group(2)), _column_index(match.group(1))


def _check_sheet_extents(zf: zipfile.ZipFile) -> None:
    """Bound explicit/implicit cells and merged allocations without building a grid."""
    for name in _worksheet_paths(zf):
        current_row = current_column = cell_count = 0
        with zf.open(name) as sheet_file:
            for event, elem in iterparse(sheet_file, events=("start", "end")):
                tag = elem.tag.rsplit("}", 1)[-1]
                if event == "end":
                    elem.clear()
                    continue
                if tag == "row":
                    raw_row = elem.get("r")
                    if raw_row is None:
                        current_row += 1
                    else:
                        try:
                            current_row = int(raw_row)
                        except ValueError:
                            numeric_row = float(raw_row)
                            if not numeric_row.is_integer():
                                raise ValueError("invalid row number")
                            current_row = int(numeric_row)
                    current_column = 0
                elif tag == "c":
                    ref = elem.get("r")
                    if ref:
                        row, current_column = _cell_coordinate(ref)
                    else:
                        row = current_row
                        current_column += 1
                    _check_coordinate(name, row, current_column)
                    cell_count += 1
                elif tag == "mergeCell":
                    ref = elem.get("ref", "")
                    endpoints = ref.replace("$", "").split(":")
                    if len(endpoints) not in (1, 2):
                        raise InvalidWorkbookError("invalid_workbook", "invalid merged range")
                    first_row, first_col = _cell_coordinate(endpoints[0])
                    last_row, last_col = _cell_coordinate(endpoints[-1])
                    _check_coordinate(name, first_row, first_col)
                    _check_coordinate(name, last_row, last_col)
                    if first_row > last_row or first_col > last_col:
                        raise InvalidWorkbookError("invalid_workbook", "reversed merged range")
                    # Count cumulative work conservatively, including overlapping ranges.
                    cell_count += (last_row - first_row + 1) * (last_col - first_col + 1)
                if cell_count > MAX_CELLS:
                    raise WorkbookTooLargeError("max_cells", f"{name} {cell_count} cells")


def check_workbook_limits(data: bytes) -> None:
    """Raises `WorkbookTooLargeError` over a cap, `InvalidWorkbookError` if malformed."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            _check_declared_zip_bounds(zf)
            _check_member_allowlist(zf)
            _check_actual_decompressed_size(zf)
            _check_sheet_extents(zf)
    except WorkbookRejectedError:
        raise
    except Exception as exc:
        raise InvalidWorkbookError("invalid_workbook", str(exc)) from exc
