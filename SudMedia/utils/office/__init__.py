"""Outils d'automatisation LibreOffice pour les documents bureautiques."""

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
    "SPREADSHEET_EXTENSIONS",
    "OfficeConversionError",
    "SpreadsheetPdfResult",
    "collect_spreadsheets",
    "convert_spreadsheet_to_pdf",
    "find_excel",
    "find_soffice",
]
