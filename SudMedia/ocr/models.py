"""Modèles de résultats de Sud OCR."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class OCRPage:
    number: int
    text: str
    source: str


@dataclass(frozen=True)
class OCRDocument:
    source_path: Path
    pages: tuple[OCRPage, ...]

    @property
    def text(self) -> str:
        return "\n\n".join(page.text.strip() for page in self.pages if page.text.strip())


@dataclass
class OCRResult:
    documents: list[OCRDocument] = field(default_factory=list)
    outputs: list[Path] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
