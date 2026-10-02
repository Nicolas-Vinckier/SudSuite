"""Outils de traitement et conversion de documents bureautiques."""

from .docx_optimizer import (
    DOCX_EXTENSIONS,
    DocxMediaChange,
    DocxOptimizationError,
    DocxOptimizationResult,
    collect_docx,
    optimize_docx,
    verify_docx_package,
)

from .spreadsheet_pdf import (
    SPREADSHEET_EXTENSIONS,
    OfficeConversionError,
    SpreadsheetPdfResult,
    collect_spreadsheets,
    convert_spreadsheet_to_pdf,
    find_excel,
    find_soffice,
)

__all__ = [
    "DOCX_EXTENSIONS",
    "DocxMediaChange",
    "DocxOptimizationError",
    "DocxOptimizationResult",
    "SPREADSHEET_EXTENSIONS",
    "OfficeConversionError",
    "SpreadsheetPdfResult",
    "collect_spreadsheets",
    "collect_docx",
    "convert_spreadsheet_to_pdf",
    "find_excel",
    "find_soffice",
    "optimize_docx",
    "verify_docx_package",
]
