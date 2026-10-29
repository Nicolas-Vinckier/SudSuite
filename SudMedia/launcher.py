"""Point d'entrée de SudMedia : menu des outils images, documents et archives."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from SudCore.launcher import Entry, launch

TITLE = "SudMedia"
DESCRIPTION = "Images, documents, archives et OCR"

TOOLS: tuple[Entry, ...] = (
    Entry("compressor", "Sud Compressor", "compresse les images", "SudMedia.image_compressor"),
    Entry("sorting", "Sud Sorting", "trie les médias par date", "SudMedia.image_sorting"),
    Entry("rename", "Sud Rename", "renomme les fichiers en masse", "SudMedia.image_renamer"),
    Entry("convert", "Sud Convert", "convertit les formats d'images", "SudMedia.image_convertissor"),
    Entry("resize", "Sud Resize", "redimensionne les images", "SudMedia.image_resizer"),
    Entry("master", "Sud Master", "resize + convert + compress", "SudMedia.image_master"),
    Entry("pdf2img", "Sud PDF to Image", "PDF vers images", "SudMedia.pdf_to_image"),
    Entry("excel2pdf", "Sud Excel to PDF", "tableurs vers PDF", "SudMedia.excel_to_pdf"),
    Entry("archive", "Sud Archive", "compresse/décompresse des dossiers", "SudMedia.folder_compressor"),
    Entry("weight", "Sud Weight", "analyse le poids d'un dossier", "SudMedia.folder_weight"),
    Entry("duplicate", "Sud Duplicate", "détecte les doublons", "SudMedia.sud_duplicate"),
    Entry("ocr", "Sud OCR", "extrait le texte des documents", "SudMedia.sud_ocr"),
    Entry("docx", "Sud DOCX Optimizer", "allège les documents Word", "SudMedia.docx_optimizer"),
    Entry("qr", "Sud QR Code", "génère des QR codes", "SudMedia.qr_code_generator"),
)


def main(argv: Sequence[str] | None = None) -> int:
    return launch(TITLE, TOOLS, argv)


if __name__ == "__main__":
    sys.exit(main())
