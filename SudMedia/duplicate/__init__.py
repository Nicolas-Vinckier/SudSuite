"""Façade de compatibilité pour Sud Duplicate.

La logique réside désormais dans ``SudMedia.utils.duplicate``, ``SudMedia.utils.hashing`` et ``SudMedia.utils.filesystem``.
"""

from __future__ import annotations

try:
    from ..utils.duplicate import (
        DuplicateGroup,
        DuplicateReport,
        FileCandidate,
        QuarantineResult,
        quarantine_duplicates,
        scan_duplicates,
    )
except ImportError:
    from utils.duplicate import (
        DuplicateGroup,
        DuplicateReport,
        FileCandidate,
        QuarantineResult,
        quarantine_duplicates,
        scan_duplicates,
    )

__all__ = [
    "DuplicateGroup",
    "DuplicateReport",
    "FileCandidate",
    "QuarantineResult",
    "quarantine_duplicates",
    "scan_duplicates",
]
