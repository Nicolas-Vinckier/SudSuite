"""Module duplicate : détection, analyse et mise en quarantaine des doublons."""

from .actions import QuarantineResult, quarantine_duplicates
from .models import DuplicateGroup, DuplicateReport, FileCandidate
from .scanner import scan_duplicates

__all__ = [
    "DuplicateGroup",
    "DuplicateReport",
    "FileCandidate",
    "QuarantineResult",
    "quarantine_duplicates",
    "scan_duplicates",
]
